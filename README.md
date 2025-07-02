# bega_mon
## A Cross-Chain Bridge Event Listener Simulation

This repository contains a Python-based simulation of a cross-chain bridge event listener. This component is a critical piece of off-chain infrastructure for any decentralized bridge, responsible for monitoring events on a source blockchain and triggering corresponding actions on a destination chain.

This script is designed to be architecturally robust, demonstrating best practices such as separation of concerns, configuration management, and resilient error handling.

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
    *   **Responsibility**: Manages all direct communication with a source chain's RPC node using the `web3.py` library.
    *   **Key Functions**: Establishes and maintains a connection, fetches the latest block number, and retrieves event logs for specified block ranges.
    *   **Features**: Includes connection retry logic with exponential backoff.

*   `EventProcessor`:
    *   **Responsibility**: Decodes and transforms raw blockchain event logs into structured, human-readable data.
    *   **Key Functions**: Takes a raw log from the `BlockchainConnector` and uses the contract's ABI to parse it into a clean dictionary containing event parameters like `user`, `amount`, etc.

*   `CrossChainDispatcher`:
    *   **Responsibility**: Simulates the action of relaying the event information to the destination chain.
    *   **Key Functions**: Constructs a JSON payload from the processed event data and sends it via an HTTP POST request to a mock API endpoint using the `requests` library.
    *   **Features**: Includes retry logic for API requests to handle temporary network or service issues.

*   `BridgeContractMonitor`:
    *   **Responsibility**: The central orchestrator. It coordinates the other components to run the end-to-end monitoring process.
    *   **Key Functions**: Contains the main simulation loop that periodically checks for new blocks, fetches logs, processes them, and dispatches them. It also manages the state, such as tracking the last successfully scanned block number.

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

---

### How it Works

1.  **Initialization**: The `main` function instantiates the `BridgeContractMonitor`, which in turn sets up the `BlockchainConnector`, `EventProcessor`, and `CrossChainDispatcher` with configuration loaded from a `.env` file.

2.  **Starting Point**: The monitor determines a starting block to scan from. In this simulation, it starts 100 blocks behind the current chain head to ensure it has a buffer. In a production system, it would load the last scanned block from a persistent database or file.

3.  **Polling Loop**: The monitor enters an infinite `asyncio` loop where it:
    a.  Fetches the latest block number from the source chain.
    b.  Calculates a `to_block` number by subtracting a confirmation delay (e.g., 6 blocks) from the latest block. This prevents processing transactions that might be reversed in a reorg.
    c.  If `to_block` is greater than the `last_scanned_block`, it requests all logs for the `TokensLocked` event between these two blocks.
    d.  For each log found, it is passed to the `EventProcessor` to be decoded.
    e.  The resulting structured data is passed to the `CrossChainDispatcher`.
    f.  The dispatcher sends the data to the configured mock API endpoint.
    g.  After scanning the range, the `last_scanned_block` is updated to `to_block`.

4.  **Error Handling**: If an RPC connection drops or an API call fails, the respective components will automatically retry the operation several times before logging a critical error.

---

### Usage Example

1.  **Clone the repository:**
    ```bash
    git clone <repository-url>
    cd bega_mon
    ```

2.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

3.  **Configure environment variables:**
    Create a file named `.env` in the root directory and add the following configuration. You will need an RPC URL for an Ethereum-compatible chain (e.g., from Infura or Alchemy).

    ```env
    # .env file
    
    # RPC URL for the source chain (e.g., Ethereum Sepolia testnet)
    SOURCE_CHAIN_RPC_URL="https://rpc.sepolia.org"
    
    # Address of the bridge contract to monitor (use a real one if you have it, otherwise placeholder is fine for simulation)
    BRIDGE_CONTRACT_ADDRESS="0xc5a61774B7a238B213133A52373079015A75438A"
    
    # The API endpoint of the destination chain's relayer service (mocked)
    DESTINATION_API_ENDPOINT="https://jsonplaceholder.typicode.com/posts" # Using a public mock API for testing
    ```

4.  **Run the script:**
    ```bash
    python script.py
    ```

5.  **Expected Output:**
    The script will start logging its activities to the console. You will see messages about connecting to the blockchain, scanning block ranges, and hopefully finding and processing events if the configured contract has any.

    ```
    2023-10-27 15:30:00 - INFO - [script:235] - --- BegaMon Cross-Chain Bridge Monitor Simulation ---
    
    2023-10-27 15:30:01 - INFO - [script:74] - Attempting to connect to blockchain node at https://rpc.sepolia.org...
    2023-10-27 15:30:02 - INFO - [script:78] - Successfully connected to blockchain node.
    2023-10-27 15:30:02 - INFO - [script:80] - Connected to Chain ID: 11155111
    2023-10-27 15:30:03 - INFO - [script:205] - Determined starting block for scan: 4750100
    2023-10-27 15:30:03 - INFO - [script:214] - Starting bridge event monitoring loop...
    2023-10-27 15:30:04 - INFO - [script:221] - Scanning blocks from 4750101 to 4750195...
    2023-10-27 15:30:05 - INFO - [script:231] - No new events found in this range.
    2023-10-27 15:30:20 - INFO - [script:234] - No new confirmed blocks to process. Current head: 4750201, last scanned: 4750195
    ...
    ```
