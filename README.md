# BegaMon
## A Cross-Chain Bridge Event Listener Simulation

This repository contains a Python-based simulation of a cross-chain bridge event listener. This component is a critical piece of the off-chain infrastructure required for any decentralized bridge. It is responsible for monitoring events on a source blockchain and triggering corresponding actions on a destination chain.

The application is designed to be architecturally robust, demonstrating best practices such as separation of concerns, configuration management, and resilient error handling.

---

### Concept

A cross-chain bridge allows users to transfer assets or data from one blockchain (the 'source chain') to another (the 'destination chain'). A common mechanism for this is 'lock-and-mint'.

1.  **Lock**: A user sends tokens to a smart contract on the source chain, which locks them.
2.  **Event Emission**: The smart contract emits an event (e.g., `TokensLocked`) containing details of the transaction (user, token, amount, destination address).
3.  **Listen**: An off-chain service, the 'event listener' or 'relayer', constantly monitors the source chain for this specific event.
4.  **Validate**: Upon detecting the event, the listener waits for a few block confirmations to ensure the transaction is final and not part of a blockchain reorganization (reorg).
5.  **Dispatch**: The listener then securely communicates with a contract on the destination chain, instructing it to 'mint' an equivalent amount of a wrapped token and send it to the user's destination address.

This project simulates the **listener** and **dispatcher** components (steps 3-5).

---

### Code Architecture

The script is divided into several distinct classes, each with a single responsibility. This makes the system modular, easier to test, and more understandable.

*   `BlockchainConnector`:
    *   **Responsibility**: Manages all direct communication with the source chain's RPC node using the `web3.py` library.
    *   **Key Functions**: Establishes and maintains a connection, fetches the latest block number, and retrieves event logs for specified block ranges.
    *   **Features**: Includes connection retry logic with exponential backoff.

*   `EventProcessor`:
    *   **Responsibility**: Decodes and transforms raw blockchain event logs into structured, application-friendly data.
    *   **Key Functions**: Parses raw event logs from the `BlockchainConnector` using the contract's ABI, transforming them into structured dictionaries containing event parameters like `user`, `amount`, etc.

*   `CrossChainDispatcher`:
    *   **Responsibility**: Simulates the action of relaying the event information to the destination chain.
    *   **Key Functions**: Formats the processed event data into a JSON payload and dispatches it to a destination API endpoint via an HTTP POST request using the `requests` library.
    *   **Features**: Includes retry logic for API requests to handle temporary network or service issues.

*   `BridgeContractMonitor`:
    *   **Responsibility**: The central orchestrator that coordinates all other components to run the end-to-end monitoring process.
    *   **Key Functions**: Manages the main simulation loop that periodically checks for new blocks, fetches logs, processes them, and dispatches them. It also manages state, such as tracking the last successfully scanned block number.

#### Data Flow

```
[RPC Node] <--> (1. Get Blocks/Logs) <--> [BlockchainConnector]
                                                 |
                                                 |
(2. Raw Logs) -----------------------------------> [BridgeContractMonitor]
                                                 |         ^
                                                 |         |
                           (3. Process Log)      V         |
                                             [EventProcessor]    (4. Dispatch Action)
                                                 |         |
                                                 |         |
                                                 V         |
                                             [CrossChainDispatcher] --- (5. POST Request) ---> [Destination API]
```

#### Orchestration Example

The following snippet from `script.py` shows how the individual components are instantiated and orchestrated by the main function.

```python
# A simplified view of the main function in script.py

async def main():
    # Load configuration from .env file
    config = get_config()

    # Instantiate components
    connector = BlockchainConnector(rpc_url=config.rpc_url)
    processor = EventProcessor(contract_abi=config.contract_abi)
    dispatcher = CrossChainDispatcher(api_endpoint=config.api_endpoint)
    
    # Create and run the monitor
    monitor = BridgeContractMonitor(
        config=config,
        connector=connector,
        processor=processor,
        dispatcher=dispatcher
    )
    await monitor.run()

if __name__ == "__main__":
    asyncio.run(main())
```

---

### How It Works

1.  **Initialization**: The `main` function instantiates the `BridgeContractMonitor`, which in turn sets up the `BlockchainConnector`, `EventProcessor`, and `CrossChainDispatcher` with configuration loaded from a `.env` file.

2.  **Starting Point**: The monitor determines a starting block to scan from. In this simulation, it starts 100 blocks behind the current chain head to provide a buffer. In a production system, this value would be loaded from a persistent store (like a database or file) to resume scanning from the last known block.

3.  **Polling Loop**: The monitor enters an infinite `asyncio` loop where it:
    a.  Fetches the latest block number from the source chain.
    b.  Calculates a `to_block` number by subtracting a confirmation delay (e.g., 6 blocks) from the latest block. This prevents processing transactions that might be reversed in a reorg.
    c.  If new blocks have been confirmed (i.e., `to_block` > `last_scanned_block`), it requests all `TokensLocked` event logs within this new block range.
    d.  Each found log is passed to the `EventProcessor` for decoding.
    e.  The resulting structured data is then passed to the `CrossChainDispatcher`.
    f.  The dispatcher sends this data to the configured mock API endpoint.
    g.  After successfully scanning the range, it updates `last_scanned_block` to `to_block` to mark its progress.

4.  **Error Handling**: If an RPC connection drops or an API call fails, the respective components will automatically retry the operation several times before logging a critical error.

---

### Usage

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/your-github-username/BegaMon.git
    cd BegaMon
    ```

2.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

3.  **Configure environment variables:**
    Create a `.env` file in the root directory and add the following configuration. You will need an RPC URL for an Ethereum-compatible chain (e.g., from Infura or Alchemy).

    *Note: The `.env` file contains sensitive information and should be added to your `.gitignore` to prevent committing it to version control.*

    ```env
    # .env file
    
    # RPC URL for the source chain (e.g., Ethereum Sepolia testnet)
    SOURCE_CHAIN_RPC_URL="https://rpc.sepolia.org"
    
    # Address of the bridge contract to monitor
    BRIDGE_CONTRACT_ADDRESS="0xc5a61774B7a238B213133A52373079015A75438A"
    
    # The API endpoint of the destination chain's relayer service (mocked)
    DESTINATION_API_ENDPOINT="https://jsonplaceholder.typicode.com/posts" # A public mock API for testing
    ```

4.  **Add Contract ABI:**
    The script needs the contract's Application Binary Interface (ABI) to correctly interpret and decode event data. Create a file named `abi.json` in the root directory containing the ABI for the event you are monitoring. For a `TokensLocked` event, it would look something like this:

    ```json
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
            "indexed": false,
            "internalType": "uint256",
            "name": "amount",
            "type": "uint256"
          }
        ],
        "name": "TokensLocked",
        "type": "event"
      }
    ]
    ```

5.  **Run the monitor:**
    ```bash
    python script.py
    ```

6.  **Expected Output:**
    The script will start logging its activities to the console. You will see messages about connecting to the blockchain and scanning block ranges. If the monitored contract has emitted events in the scanned range, you will also see logs for them being processed and dispatched.

    The output will look similar to the following (note: actual block numbers and timestamps will vary):

    ```
    YYYY-MM-DD HH:MM:SS - INFO - --- BegaMon Cross-Chain Bridge Monitor Simulation ---
    
    YYYY-MM-DD HH:MM:SS - INFO - Attempting to connect to blockchain node at https://rpc.sepolia.org...
    YYYY-MM-DD HH:MM:SS - INFO - Successfully connected to blockchain node.
    YYYY-MM-DD HH:MM:SS - INFO - Connected to Chain ID: 11155111
    YYYY-MM-DD HH:MM:SS - INFO - Determined starting block for scan: 4750100
    YYYY-MM-DD HH:MM:SS - INFO - Starting bridge event monitoring loop...
    YYYY-MM-DD HH:MM:SS - INFO - Scanning blocks from 4750101 to 4750195...
    YYYY-MM-DD HH:MM:SS - INFO - No new events found in this range.
    YYYY-MM-DD HH:MM:SS - INFO - No new confirmed blocks to process. Current head: 4750201, last scanned: 4750195
    ...
    ```