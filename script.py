import os
import json
import time
import logging
import asyncio
import requests
from typing import Dict, Any, List, Optional

from web3 import Web3
from web3.types import LogReceipt, BlockData
from web3.exceptions import TransactionNotFound
from dotenv import load_dotenv

# --- Basic Configuration ---
# Load environment variables from a .env file for security and flexibility.
load_dotenv()

# Setup a comprehensive logger
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - [%(module)s:%(lineno)d] - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

logger = logging.getLogger(__name__)

# --- Configuration Loading ---
# It's a best practice to keep configuration separate from the code.
# This allows for easy adjustments without modifying the core logic.
CONFIG = {
    "SOURCE_CHAIN_RPC_URL": os.getenv("SOURCE_CHAIN_RPC_URL", "https://rpc.sepolia.org"),
    "BRIDGE_CONTRACT_ADDRESS": os.getenv("BRIDGE_CONTRACT_ADDRESS", "0x0000000000000000000000000000000000000000"), # Placeholder address
    "DESTINATION_API_ENDPOINT": os.getenv("DESTINATION_API_ENDPOINT", "https://api.mock-destination-chain.com/mint"),
    "POLL_INTERVAL_SECONDS": 15,
    "CONFIRMATION_BLOCKS": 6, # Number of blocks to wait for to consider a transaction final (mitigates reorgs)
    "MAX_RETRY_ATTEMPTS": 5,
    "RETRY_DELAY_SECONDS": 5
}

# --- Contract ABI ---
# A simplified ABI for a hypothetical cross-chain bridge contract.
# It only contains the event we are interested in: 'TokensLocked'.
BRIDGE_CONTRACT_ABI = json.loads('''
[
  {
    "anonymous": false,
    "inputs": [
      {
        "indexed": true,
        "internalType": "address",
        "name": "user",
        "type": "address"
      },
      {
        "indexed": true,
        "internalType": "address",
        "name": "token",
        "type": "address"
      },
      {
        "indexed": false,
        "internalType": "uint256",
        "name": "amount",
        "type": "uint256"
      },
      {
        "indexed": true,
        "internalType": "bytes32",
        "name": "destinationChainId",
        "type": "bytes32"
      },
      {
        "indexed": false,
        "internalType": "address",
        "name": "recipient",
        "type": "address"
      }
    ],
    "name": "TokensLocked",
    "type": "event"
  }
]
''')

class BlockchainConnector:
    """Handles all direct interactions with a blockchain node via Web3.py."""

    def __init__(self, rpc_url: str):
        """Initializes the connector with a specific RPC endpoint.

        Args:
            rpc_url (str): The HTTP/WSS URL of the blockchain node.
        """
        self.rpc_url = rpc_url
        self.web3 = None
        self.connect()

    def connect(self) -> None:
        """Establishes a connection to the blockchain node with retry logic."""
        logger.info(f"Attempting to connect to blockchain node at {self.rpc_url}...")
        for attempt in range(CONFIG['MAX_RETRY_ATTEMPTS']):
            try:
                self.web3 = Web3(Web3.HTTPProvider(self.rpc_url))
                if self.web3.is_connected():
                    logger.info("Successfully connected to blockchain node.")
                    chain_id = self.web3.eth.chain_id
                    logger.info(f"Connected to Chain ID: {chain_id}")
                    return
                else:
                    raise ConnectionError("Web3 provider reports not connected.")
            except Exception as e:
                logger.error(f"Connection attempt {attempt + 1} failed: {e}")
                if attempt < CONFIG['MAX_RETRY_ATTEMPTS'] - 1:
                    time.sleep(CONFIG['RETRY_DELAY_SECONDS'] * (attempt + 1)) # Exponential backoff
                else:
                    logger.critical("Could not establish connection to the blockchain node. Exiting.")
                    raise

    def get_latest_block_number(self) -> int:
        """Fetches the most recent block number from the blockchain."""
        try:
            return self.web3.eth.block_number
        except Exception as e:
            logger.error(f"Failed to get latest block number: {e}. Attempting to reconnect...")
            self.connect() # Attempt to re-establish connection
            return self.web3.eth.block_number

    def get_logs_for_range(self, from_block: int, to_block: int, address: str, topics: List[str]) -> List[LogReceipt]:
        """Retrieves event logs for a specific contract and topic within a block range."""
        logger.debug(f"Fetching logs from block {from_block} to {to_block} for address {address}.")
        try:
            return self.web3.eth.get_logs({
                'fromBlock': from_block,
                'toBlock': to_block,
                'address': address,
                'topics': topics
            })
        except Exception as e:
            logger.error(f"Error fetching logs for range {from_block}-{to_block}: {e}")
            return []

class EventProcessor:
    """Parses and validates raw event logs into a structured format."""

    def __init__(self, abi: List[Dict[str, Any]]):
        """Initializes the processor with the contract's ABI."""
        self.contract = Web3().eth.contract(abi=abi) # Create a temporary contract object for event decoding
        logger.info("EventProcessor initialized.")

    def process_log(self, log: LogReceipt) -> Optional[Dict[str, Any]]:
        """Processes a single raw log into a structured dictionary.

        Args:
            log (LogReceipt): The raw log data from get_logs.

        Returns:
            Optional[Dict[str, Any]]: A dictionary with parsed event data or None if parsing fails.
        """
        try:
            # The web3.py contract object can decode logs for its known events
            event_data = self.contract.events.TokensLocked().process_log(log)
            processed_event = {
                'transaction_hash': event_data['transactionHash'].hex(),
                'block_number': event_data['blockNumber'],
                'user': event_data['args']['user'],
                'token': event_data['args']['token'],
                'amount': event_data['args']['amount'],
                'destination_chain_id': event_data['args']['destinationChainId'].hex(),
                'recipient': event_data['args']['recipient']
            }
            logger.info(f"Successfully processed event from tx {processed_event['transaction_hash']}")
            return processed_event
        except Exception as e:
            # This can happen if the log topic matches but the data format is unexpected.
            logger.error(f"Failed to process log: {log}. Error: {e}")
            return None

class CrossChainDispatcher:
    """Simulates dispatching the cross-chain action to a destination chain relayer/API."""

    def __init__(self, api_endpoint: str):
        """Initializes the dispatcher with the target API endpoint."""
        self.api_endpoint = api_endpoint
        self.session = requests.Session()
        self.session.headers.update({
            'Content-Type': 'application/json',
            'User-Agent': 'bega_mon-bridge-simulator/1.0'
        })
        logger.info(f"CrossChainDispatcher initialized for endpoint: {self.api_endpoint}")

    def dispatch_mint_request(self, event_data: Dict[str, Any]) -> bool:
        """Sends a POST request to the destination API to trigger a minting operation.

        Args:
            event_data (Dict[str, Any]): The processed event data.

        Returns:
            bool: True if the request was successful, False otherwise.
        """
        payload = {
            "sourceTransactionHash": event_data['transaction_hash'],
            "recipient": event_data['recipient'],
            "token": event_data['token'],
            "amount": str(event_data['amount']), # APIs often prefer amounts as strings
            "destinationChainId": event_data['destination_chain_id']
        }
        logger.info(f"Dispatching mint request for tx {payload['sourceTransactionHash']}...")

        for attempt in range(CONFIG['MAX_RETRY_ATTEMPTS']):
            try:
                response = self.session.post(self.api_endpoint, json=payload, timeout=10)
                response.raise_for_status() # Raises an HTTPError for bad responses (4xx or 5xx)
                logger.info(f"Successfully dispatched request. API response: {response.json()}")
                return True
            except requests.exceptions.RequestException as e:
                logger.warning(f"Dispatch attempt {attempt + 1} failed for tx {payload['sourceTransactionHash']}: {e}")
                if attempt < CONFIG['MAX_RETRY_ATTEMPTS'] - 1:
                    time.sleep(CONFIG['RETRY_DELAY_SECONDS'])
                else:
                    logger.error(f"Failed to dispatch mint request for tx {payload['sourceTransactionHash']} after all retries.")
                    return False

class BridgeContractMonitor:
    """The main orchestrator that monitors the bridge contract for events."""

    def __init__(self, config: Dict[str, Any]):
        """Initializes the monitor and its dependencies."""
        self.config = config
        self.connector = BlockchainConnector(config["SOURCE_CHAIN_RPC_URL"])
        self.processor = EventProcessor(BRIDGE_CONTRACT_ABI)
        self.dispatcher = CrossChainDispatcher(config["DESTINATION_API_ENDPOINT"])
        self.contract_address = self.connector.web3.to_checksum_address(config["BRIDGE_CONTRACT_ADDRESS"])
        self.last_scanned_block = self._get_starting_block()
        # Get the event topic hash for 'TokensLocked' to filter logs efficiently
        self.event_topic = self.connector.web3.keccak(text="TokensLocked(address,address,uint256,bytes32,address)").hex()

    def _get_starting_block(self) -> int:
        """Determines the starting block for scanning, e.g., from a state file or current block."""
        # In a real application, this would load the last processed block from a file/database.
        # For this simulation, we start from a few blocks behind the current head.
        try:
            current_block = self.connector.get_latest_block_number()
            start_block = max(0, current_block - 100) # Start scanning the last 100 blocks
            logger.info(f"Determined starting block for scan: {start_block}")
            return start_block
        except Exception as e:
            logger.critical(f"Could not determine starting block. Error: {e}")
            exit(1)

    async def run_simulation_loop(self) -> None:
        """The main async loop that continuously scans for new blocks and events."""
        logger.info("Starting bridge event monitoring loop...")
        while True:
            try:
                latest_block = self.connector.get_latest_block_number()
                # The 'to_block' is calculated to ensure we only process confirmed blocks.
                to_block = latest_block - self.config['CONFIRMATION_BLOCKS']

                if to_block > self.last_scanned_block:
                    logger.info(f"Scanning blocks from {self.last_scanned_block + 1} to {to_block}...")
                    logs = self.connector.get_logs_for_range(
                        from_block=self.last_scanned_block + 1,
                        to_block=to_block,
                        address=self.contract_address,
                        topics=[self.event_topic]
                    )

                    if logs:
                        logger.info(f"Found {len(logs)} potential event(s) in block range.")
                        for log in logs:
                            processed_event = self.processor.process_log(log)
                            if processed_event:
                                self.dispatcher.dispatch_mint_request(processed_event)
                    else:
                        logger.info("No new events found in this range.")

                    # Update state ONLY after successful processing
                    self.last_scanned_block = to_block
                    # In a real app, you would save `self.last_scanned_block` to a persistent file here.

                else:
                    logger.info(f"No new confirmed blocks to process. Current head: {latest_block}, last scanned: {self.last_scanned_block}")

            except Exception as e:
                logger.error(f"An unexpected error occurred in the main loop: {e}", exc_info=True)

            # Wait for the next poll interval
            await asyncio.sleep(self.config['POLL_INTERVAL_SECONDS'])


def main():
    """Entry point for the script."""
    logger.info("--- BegaMon Cross-Chain Bridge Monitor Simulation ---_n")
    try:
        monitor = BridgeContractMonitor(CONFIG)
        asyncio.run(monitor.run_simulation_loop())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Simulation stopped by user.")
    except Exception as e:
        logger.critical(f"A critical error forced the simulation to stop: {e}", exc_info=True)

if __name__ == "__main__":
    main()



# @-internal-utility-start
def is_api_key_valid_5619(api_key: str):
    """Checks if the API key format is valid. Added on 2025-11-03 13:47:02"""
    import re
    return bool(re.match(r'^[a-zA-Z0-9]{32}$', api_key))
# @-internal-utility-end

