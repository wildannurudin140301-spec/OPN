import json
import time
import random
from web3 import Web3
from eth_account import Account
from datetime import datetime
from colorama import init, Fore, Style
import os
import sys
from eth_abi import encode

init(autoreset=True)

# ============================================
# CONFIGURATION
# ============================================

class Config:
    RPC_URL = "https://testnet-rpc.iopn.tech/"
    CHAIN_ID = 984
    EXPLORER_URL = "https://testnet.iopn.tech"
    
    ROUTER_ADDRESS = "0xB489bce5c9c9364da2D1D1Bc5CE4274F63141885"  
    WOPN_ADDRESS = "0xBc022C9dEb5AF250A526321d16Ef52E39b4DBD84"    
    OPNT_ADDRESS = "0x2aEc1Db9197Ff284011A6A1d0752AD03F5782B0d"    
    TUSDT_ADDRESS = "0x3e01b4d892E0D0A219eF8BBe7e260a6bc8d9B31b"
    VINTAGE_ADDRESS = "0x8E92E336Cf831a8159F8636c138561d5A7103595"
    
    PRIVATE_KEY_FILE = "pv.txt"
    FIXED_SWAP_AMOUNT = "0.001"
    SLIPPAGE_BPS = 500  # 5% slippage
    
    GAS_LIMITS = {
        'swap': 250000,
        'approve': 100000,
        'wrap': 120000,
    }
    
    MIN_GAS_PRICE = Web3.to_wei(10, 'gwei')
    DEFAULT_GAS_PRICE = Web3.to_wei(15, 'gwei')
    HIGH_GAS_PRICE = Web3.to_wei(25, 'gwei')

SELECTORS = {
    'SWAP_NATIVE_FOR_TOKENS': '0xa24fefef',
    'SWAP_TOKENS_FOR_NATIVE': '0xe0f44df2',
}

# ============================================
# TRADING PAIRS
# ============================================

SWAP_PAIRS = [
    {'from': 'ETH', 'to': Config.OPNT_ADDRESS, 'name': 'OPN->OPNT', 'weight': 90},
    {'from': 'ETH', 'to': Config.TUSDT_ADDRESS, 'name': 'OPN->tUSDT', 'weight': 1},
    {'from': 'ETH', 'to': Config.VINTAGE_ADDRESS, 'name': 'OPN->VINTAGE', 'weight': 1},
    {'from': Config.OPNT_ADDRESS, 'to': 'ETH', 'name': 'OPNT->OPN', 'weight': 90},
    {'from': Config.TUSDT_ADDRESS, 'to': 'ETH', 'name': 'tUSDT->OPN', 'weight': 1},
    {'from': Config.VINTAGE_ADDRESS, 'to': 'ETH', 'name': 'VINTAGE->OPN', 'weight': 1},
]

# ============================================
# ABI DEFINITIONS
# ============================================

ROUTER_ABI = json.loads('''[
    {
        "inputs": [
            {"internalType": "uint256", "name": "amountIn", "type": "uint256"},
            {"internalType": "uint256", "name": "amountOutMin", "type": "uint256"},
            {"internalType": "address[]", "name": "path", "type": "address[]"},
            {"internalType": "address", "name": "to", "type": "address"},
            {"internalType": "uint256", "name": "deadline", "type": "uint256"}
        ],
        "name": "swapExactTokensForTokens",
        "outputs": [{"internalType": "uint256[]", "name": "amounts", "type": "uint256[]"}],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "inputs": [
            {"internalType": "uint256", "name": "amountIn", "type": "uint256"},
            {"internalType": "address[]", "name": "path", "type": "address[]"}
        ],
        "name": "getAmountsOut",
        "outputs": [{"internalType": "uint256[]", "name": "amounts", "type": "uint256[]"}],
        "stateMutability": "view",
        "type": "function"
    }
]''')

ERC20_ABI = json.loads('''[
    {
        "constant": true,
        "inputs": [{"name": "_owner", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "balance", "type": "uint256"}],
        "type": "function"
    },
    {
        "constant": false,
        "inputs": [
            {"name": "_spender", "type": "address"},
            {"name": "_value", "type": "uint256"}
        ],
        "name": "approve",
        "outputs": [{"name": "", "type": "bool"}],
        "type": "function"
    },
    {
        "constant": true,
        "inputs": [
            {"name": "_owner", "type": "address"},
            {"name": "_spender", "type": "address"}
        ],
        "name": "allowance",
        "outputs": [{"name": "", "type": "uint256"}],
        "type": "function"
    },
    {
        "constant": false,
        "inputs": [],
        "name": "deposit",
        "outputs": [],
        "stateMutability": "payable",
        "type": "function"
    },
    {
        "constant": false,
        "inputs": [{"name": "wad", "type": "uint256"}],
        "name": "withdraw",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function"
    }
]''')

# ============================================
# UTILITY FUNCTIONS
# ============================================

def print_banner():
    print(Fore.CYAN + Style.BRIGHT + "="*70)
    print(Fore.YELLOW + Style.BRIGHT + "          OPN TESTNET AUTO SWAP BOT ")
    print(Fore.GREEN + Style.BRIGHT + "        CREATED BY KAZUHA  | V1.0 ")
    print(Fore.CYAN + Style.BRIGHT + "="*70)
    print()

def select_swap_pair():
    """Select a swap pair based on weighted probability"""
    weights = [pair['weight'] for pair in SWAP_PAIRS]
    return random.choices(SWAP_PAIRS, weights=weights, k=1)[0]

def log_info(msg):
    print(Fore.CYAN + f"[INFO] {msg}")

def log_success(msg):
    print(Fore.GREEN + Style.BRIGHT + f"[SUCCESS] {msg}")

def log_error(msg):
    print(Fore.RED + Style.BRIGHT + f"[ERROR] {msg}")

def log_warn(msg):
    print(Fore.YELLOW + f"[WARN] {msg}")

def load_private_key():
    if os.path.exists(Config.PRIVATE_KEY_FILE):
        with open(Config.PRIVATE_KEY_FILE, 'r') as f:
            # pick the first non-empty, valid-hex line
            for line in f:
                s = line.strip()
                if not s:
                    continue
                if s.startswith('0x'):
                    s = s[2:]
                s = s.replace(' ', '')
                try:
                    bytes.fromhex(s)
                except ValueError:
                    continue
                return s

        # no valid key found in file -> create and append new key
        account = Account.create()
        pk = account.key.hex()[2:]
        with open(Config.PRIVATE_KEY_FILE, 'a') as f:
            f.write(pk + "\n")
        log_warn(f"New wallet created: {account.address}")
        log_warn("Please fund this address before trading!")
        return pk
    else:
        account = Account.create()
        pk = account.key.hex()[2:]
        with open(Config.PRIVATE_KEY_FILE, 'w') as f:
            f.write(pk + "\n")
        log_warn(f"New wallet created: {account.address}")
        log_warn("Please fund this address before trading!")
        return pk


def load_all_private_keys():
    keys = []
    if not os.path.exists(Config.PRIVATE_KEY_FILE):
        # will create file and return single new key
        keys.append(load_private_key())
        return keys

    with open(Config.PRIVATE_KEY_FILE, 'r') as f:
        for line in f:
            s = line.strip()
            if not s:
                continue
            if s.startswith('0x'):
                s = s[2:]
            s = s.replace(' ', '')
            try:
                bytes.fromhex(s)
            except ValueError:
                continue
            keys.append(s)

    if not keys:
        # no valid keys found -> create one
        keys.append(load_private_key())

    return keys

# ============================================
# ENCODING FUNCTIONS
# ============================================

def encode_swap_native_for_tokens(amount_out_min, path, to, deadline):
    encoded = encode(
        ['uint256', 'address[]', 'address', 'uint256'],
        [amount_out_min, path, to, deadline]
    )
    return SELECTORS['SWAP_NATIVE_FOR_TOKENS'] + encoded.hex()

def encode_swap_tokens_for_native(amount_in, amount_out_min, path, to, deadline):
    encoded = encode(
        ['uint256', 'uint256', 'address[]', 'address', 'uint256'],
        [amount_in, amount_out_min, path, to, deadline]
    )
    return SELECTORS['SWAP_TOKENS_FOR_NATIVE'] + encoded.hex()

# ============================================
# MAIN BOT CLASS
# ============================================

class OPNSwapBot:
    def __init__(self, private_key: str | None = None):
        # establish web3 connection with a few retries; do not exit process on failure
        self.w3 = Web3(Web3.HTTPProvider(Config.RPC_URL))
        max_attempts = 3
        for attempt in range(1, max_attempts + 1):
            if self.w3.is_connected():
                break
            log_warn(f"RPC connection attempt {attempt}/{max_attempts} failed, retrying...")
            time.sleep(2 * attempt)
            self.w3 = Web3(Web3.HTTPProvider(Config.RPC_URL))

        if not self.w3.is_connected():
            raise ConnectionError("Failed to connect to OPN Testnet after retries")

        if private_key:
            pk = private_key.strip()
            if pk.startswith('0x'):
                pk = pk[2:]
            pk = pk.replace(' ', '')
            try:
                bytes.fromhex(pk)
            except ValueError:
                log_error("Provided private key is not valid hex")
                raise
        else:
            pk = load_private_key()

        self.account = Account.from_key(pk)
        self.address = self.account.address
        
        self.router = self.w3.eth.contract(
            address=Web3.to_checksum_address(Config.ROUTER_ADDRESS),
            abi=ROUTER_ABI
        )
        
        self.wopn = self.w3.eth.contract(
            address=Web3.to_checksum_address(Config.WOPN_ADDRESS),
            abi=ERC20_ABI
        )
        
        log_success(f"Bot initialized | Wallet: {self.address}")
    
    def get_token_contract(self, address):
        return self.w3.eth.contract(address=Web3.to_checksum_address(address), abi=ERC20_ABI)
    
    def get_safe_gas_params(self, priority='normal'):
        try:
            gp = self.w3.eth.gas_price
            if gp < Web3.to_wei(1, 'gwei'):
                gas_price = Config.HIGH_GAS_PRICE if priority == 'high' else Config.DEFAULT_GAS_PRICE
            else:
                multiplier = 2 if priority == 'high' else 1.5
                gas_price = int(gp * multiplier)
            
            gas_price = max(gas_price, Config.MIN_GAS_PRICE)
            return {
                'maxFeePerGas': gas_price,
                'maxPriorityFeePerGas': min(gas_price, Web3.to_wei(2, 'gwei'))
            }
        except:
            return {
                'maxFeePerGas': Config.DEFAULT_GAS_PRICE,
                'maxPriorityFeePerGas': Web3.to_wei(1, 'gwei')
            }

    def _prepare_and_send(self, tx: dict, priority='normal', gas_cap=None):
        """Estimate gas safely, ensure wallet can cover fees, sign and send the tx.

        Returns the tx_hash or None on failure.
        """
        # get gas price params
        gas_params = self.get_safe_gas_params(priority)

        # try to estimate gas (use a copy without explicit gas fields)
        tx_for_estimate = {k: v for k, v in tx.items() if k not in ('gas', 'maxFeePerGas', 'maxPriorityFeePerGas')}
        try:
            estimate = self.w3.eth.estimate_gas(tx_for_estimate)
            gas_used = int(estimate * 1.2)
            if gas_used < 21000:
                gas_used = 21000
            if gas_cap is None:
                gas_cap = Config.GAS_LIMITS.get('swap', 250000)
            gas_used = min(gas_used, gas_cap)
        except Exception:
            # fallback to provided gas or configured cap
            gas_used = tx.get('gas', Config.GAS_LIMITS.get('swap', 250000))

        tx['gas'] = gas_used
        tx.update(gas_params)

        # check balance to cover gas + value
        try:
            balance = self.w3.eth.get_balance(self.address)
        except Exception:
            balance = 0

        gas_cost = gas_used * tx['maxFeePerGas']
        value = tx.get('value', 0)

        if balance < gas_cost + value:
            # try with minimum gas price fallback
            low_gp = {
                'maxFeePerGas': Config.MIN_GAS_PRICE,
                'maxPriorityFeePerGas': Web3.to_wei(1, 'gwei')
            }
            tx.update(low_gp)
            gas_cost = gas_used * tx['maxFeePerGas']
            if balance < gas_cost + value:
                log_error("Insufficient funds for gas + value. Skipping transaction.")
                return None

        try:
            signed = self.w3.eth.account.sign_transaction(tx, self.account.key)
            tx_hash = self.w3.eth.send_raw_transaction(signed.rawTransaction)
            log_info(f"Sent TX: {tx_hash.hex()}")
            return tx_hash
        except Exception as e:
            log_error(f"Failed to send transaction: {e}")
            return None
    
    def get_token_symbol(self, address):
        if address == 'ETH':
            return 'OPN'
        
        symbols = {
            Config.WOPN_ADDRESS.lower(): 'WOPN',
            Config.OPNT_ADDRESS.lower(): 'OPNT',
            Config.TUSDT_ADDRESS.lower(): 'tUSDT',
            Config.VINTAGE_ADDRESS.lower(): 'VINTAGE',
        }
        
        return symbols.get(address.lower(), 'Unknown')
    
    def approve_token(self, token_contract, spender, amount, priority='normal'):
        try:
            current = token_contract.functions.allowance(self.address, spender).call()
            if current >= amount:
                return True
            
            log_info(f"Approving {self.get_token_symbol(token_contract.address)}...")
            
            gas_params = self.get_safe_gas_params(priority)
            nonce = self.w3.eth.get_transaction_count(self.address)
            
            tx = token_contract.functions.approve(
                Web3.to_checksum_address(spender),
                Web3.to_wei(999999999, 'ether')
            ).build_transaction({
                'from': self.address,
                'nonce': nonce,
                'chainId': Config.CHAIN_ID,
            })

            tx_hash = self._prepare_and_send(tx, priority=priority, gas_cap=Config.GAS_LIMITS.get('approve', 100000))
            if not tx_hash:
                return False

            log_info(f"Approval TX: {tx_hash.hex()}")
            log_info(f"Explorer: {Config.EXPLORER_URL}/tx/{tx_hash.hex()}")

            receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=60)
            
            if receipt['status'] == 1:
                log_success("Token approved successfully")
                return True
            else:
                log_error("Approval failed")
                return False
        except Exception as e:
            log_error(f"Approval error: {str(e)}")
            return False
    
    def swap_tokens(self, token_in, token_out, amount_str, priority='normal'):
        is_native_in = (token_in == 'ETH')
        is_native_out = (token_out == 'ETH')
        
        if is_native_in and is_native_out:
            log_error("Cannot swap native to native")
            return None
        
        log_info(f"Preparing swap: {self.get_token_symbol(token_in)} -> {self.get_token_symbol(token_out)}")
        log_info(f"Amount: {amount_str}")
        
        # Build correct path
        if is_native_in:
            path = [Web3.to_checksum_address(Config.WOPN_ADDRESS), Web3.to_checksum_address(token_out)]
        elif is_native_out:
            path = [Web3.to_checksum_address(token_in), Web3.to_checksum_address(Config.WOPN_ADDRESS)]
        else:
            path = [Web3.to_checksum_address(token_in), Web3.to_checksum_address(token_out)]
        
        amount_in = Web3.to_wei(float(amount_str), 'ether')
        deadline = int(time.time()) + 1200
        
        min_out = 0
        try:
            expected = self.router.functions.getAmountsOut(amount_in, path).call()
            min_out = int(expected[-1] * (10000 - Config.SLIPPAGE_BPS) // 10000)
            log_info(f"Expected output: {Web3.from_wei(expected[-1], 'ether'):.6f} {self.get_token_symbol(token_out)}")
            log_info(f"Minimum output (5% slippage): {Web3.from_wei(min_out, 'ether'):.6f}")
        except:
            log_warn("Could not get quote, using minOut = 0")
        
        gas_params = self.get_safe_gas_params(priority)
        log_info(f"Gas price: {gas_params['maxFeePerGas'] / 10**9:.2f} gwei")
        
        try:
            if is_native_in:
                balance = self.w3.eth.get_balance(self.address)
                if balance < amount_in + Web3.to_wei(0.001, 'ether'):
                    log_error("Insufficient OPN balance")
                    return None
                
                call_data = encode_swap_native_for_tokens(min_out, path, self.address, deadline)
                nonce = self.w3.eth.get_transaction_count(self.address)
                
                log_info(f"Sending transaction (method: {SELECTORS['SWAP_NATIVE_FOR_TOKENS']})...")
                
                tx = {
                    'from': self.address,
                    'to': Config.ROUTER_ADDRESS,
                    'value': amount_in,
                    'gas': Config.GAS_LIMITS['swap'],
                    'nonce': nonce,
                    'chainId': Config.CHAIN_ID,
                    'data': call_data,
                    **gas_params
                }
                
                signed_tx = self.w3.eth.account.sign_transaction(tx, self.account.key)
                # <-- FIX
                tx_hash = self.w3.eth.send_raw_transaction(signed_tx.rawTransaction)
                
                log_success(f"Transaction sent!")
                log_success(f"TX Hash: {tx_hash.hex()}")
                log_success(f"Explorer: {Config.EXPLORER_URL}/tx/{tx_hash.hex()}")
                
                return self.wait_for_receipt(tx_hash)
                
            elif is_native_out:
                token_contract = self.get_token_contract(token_in)
                balance = token_contract.functions.balanceOf(self.address).call()
                
                if balance < amount_in:
                    log_error(f"Insufficient {self.get_token_symbol(token_in)} balance")
                    return None
                
                if not self.approve_token(token_contract, Config.ROUTER_ADDRESS, amount_in, priority):
                    return None
                
                call_data = encode_swap_tokens_for_native(amount_in, min_out, path, self.address, deadline)
                nonce = self.w3.eth.get_transaction_count(self.address)

                log_info(f"Sending transaction (method: {SELECTORS['SWAP_TOKENS_FOR_NATIVE']})...")

                tx = {
                    'from': self.address,
                    'to': Config.ROUTER_ADDRESS,
                    'value': 0,
                    'nonce': nonce,
                    'chainId': Config.CHAIN_ID,
                    'data': call_data,
                }

                try:
                    tx_hash = self._prepare_and_send(tx, priority=priority, gas_cap=Config.GAS_LIMITS.get('swap', 250000))
                    if not tx_hash:
                        return None

                    log_success(f"Transaction sent!")
                    log_success(f"TX Hash: {tx_hash.hex()}")
                    log_success(f"Explorer: {Config.EXPLORER_URL}/tx/{tx_hash.hex()}")

                    return self.wait_for_receipt(tx_hash)
                except:
                    log_warn("Custom selector failed, using fallback method...")
                    
                    nonce = self.w3.eth.get_transaction_count(self.address)
                    tx = self.router.functions.swapExactTokensForTokens(
                        amount_in, min_out, path, self.address, deadline
                    ).build_transaction({
                        'from': self.address,
                        'gas': Config.GAS_LIMITS['swap'],
                        'nonce': nonce,
                        'chainId': Config.CHAIN_ID,
                        **gas_params
                    })
                    
                    signed_tx = self.w3.eth.account.sign_transaction(tx, self.account.key)
                    # <-- FIX
                    tx_hash = self.w3.eth.send_raw_transaction(signed_tx.rawTransaction)
                    
                    log_success(f"Transaction sent!")
                    log_success(f"TX Hash: {tx_hash.hex()}")
                    log_success(f"Explorer: {Config.EXPLORER_URL}/tx/{tx_hash.hex()}")
                    
                    receipt = self.wait_for_receipt(tx_hash)
                    
                    if receipt and receipt['status'] == 1:
                        wopn_balance = self.wopn.functions.balanceOf(self.address).call()
                        if wopn_balance > 0:
                            log_info(f"Unwrapping {Web3.from_wei(wopn_balance, 'ether'):.6f} WOPN -> OPN...")
                            nonce = self.w3.eth.get_transaction_count(self.address)
                            unwrap_tx = self.wopn.functions.withdraw(wopn_balance).build_transaction({
                                'from': self.address,
                                'gas': Config.GAS_LIMITS['wrap'],
                                'nonce': nonce,
                                'chainId': Config.CHAIN_ID,
                                **gas_params
                            })
                            signed = self.w3.eth.account.sign_transaction(unwrap_tx, self.account.key)
                            # <-- FIX
                            unwrap_hash = self.w3.eth.send_raw_transaction(signed.rawTransaction)
                            log_info(f"Unwrap TX: {unwrap_hash.hex()}")
                            self.w3.eth.wait_for_transaction_receipt(unwrap_hash, timeout=60)
                            log_success("Unwrapped to OPN")
                    
                    return receipt
            
            else:
                token_contract = self.get_token_contract(token_in)
                balance = token_contract.functions.balanceOf(self.address).call()
                
                if balance < amount_in:
                    log_error(f"Insufficient {self.get_token_symbol(token_in)} balance")
                    return None
                
                if not self.approve_token(token_contract, Config.ROUTER_ADDRESS, amount_in, priority):
                    return None
                
                log_info("Building transaction...")
                
                nonce = self.w3.eth.get_transaction_count(self.address)
                tx = self.router.functions.swapExactTokensForTokens(
                    amount_in, min_out, path, self.address, deadline
                ).build_transaction({
                        'from': self.address,
                        'nonce': nonce,
                        'chainId': Config.CHAIN_ID,
                    })

                tx_hash = self._prepare_and_send(tx, priority=priority, gas_cap=Config.GAS_LIMITS.get('swap', 250000))
                if not tx_hash:
                    return None

                log_success(f"Transaction sent!")
                log_success(f"TX Hash: {tx_hash.hex()}")
                log_success(f"Explorer: {Config.EXPLORER_URL}/tx/{tx_hash.hex()}")

                return self.wait_for_receipt(tx_hash)
                
        except ValueError as e:
            error_msg = str(e)
            if 'insufficient funds' in error_msg.lower():
                log_error("Insufficient funds for gas")
            elif 'max priority fee' in error_msg.lower():
                log_warn("Gas issue, retrying with high priority...")
                return self.swap_tokens(token_in, token_out, amount_str, 'high')
            else:
                log_error(f"Transaction error: {error_msg}")
            return None
        except Exception as e:
            log_error(f"Swap failed: {str(e)}")
            return None
    
    def wait_for_receipt(self, tx_hash, timeout=120):
        log_info("Waiting for confirmation...")
        
        receipt = None
        for i in range(timeout // 2):
            try:
                receipt = self.w3.eth.get_transaction_receipt(tx_hash)
                if receipt:
                    break
            except:
                pass
            
            if i % 5 == 0 and i > 0:
                print(".", end="", flush=True)
            
            time.sleep(2)
        
        if receipt:
            print()  # New line after dots
            if receipt['status'] == 1:
                log_success("Transaction confirmed!")
                log_success(f"Block: {receipt['blockNumber']}")
                log_success(f"Gas used: {receipt['gasUsed']:,}")
                
                if 'effectiveGasPrice' in receipt:
                    gas_cost = receipt['gasUsed'] * receipt['effectiveGasPrice']
                    log_success(f"Transaction fee: {Web3.from_wei(gas_cost, 'ether'):.9f} OPN")
                
                return receipt
            else:
                log_error("Transaction failed (reverted)")
                return None
        else:
            print()
            log_warn("Transaction still pending after timeout")
            return None

# ============================================
# MAIN EXECUTION
# ============================================

def main():
    print_banner()
    
    try:
        count = int(input(Fore.CYAN + "How many swaps do you want to perform per wallet? ").strip())
        delay = int(input(Fore.CYAN + "Delay between swaps (seconds)? ").strip())

        print(Fore.GREEN + Style.BRIGHT + f"\n{'='*70}")
        log_info(f"Starting {count} random swaps per wallet with {delay}s delay")
        log_info(f"Swap amount: {Config.FIXED_SWAP_AMOUNT} tokens per swap")
        log_info(f"Bot will run continuously: cycles wallets, waits 1.5 minutes, then restarts from top of pv.txt")
        print(Fore.GREEN + Style.BRIGHT + f"{'='*70}\n")

        cycle = 0

        while True:
            cycle += 1

            # Reload keys each cycle so we always start from the first line of pv.txt
            keys = load_all_private_keys()
            total_wallets = len(keys)

            print(Fore.MAGENTA + Style.BRIGHT + f"\n{'='*70}")
            print(Fore.MAGENTA + Style.BRIGHT + f"CYCLE {cycle} - Starting new swap session")
            print(Fore.MAGENTA + Style.BRIGHT + f"{'='*70}\n")

            overall_success = 0
            overall_failed = 0

            try:
                for widx, pk in enumerate(keys, start=1):
                    try:
                        bot = OPNSwapBot(private_key=pk)
                    except Exception as e:
                        log_error(f"Skipping wallet {widx}/{total_wallets}: invalid key or init error: {e}")
                        continue

                    log_info(f"Running wallet {widx}/{total_wallets}: {bot.address}")

                    success = 0
                    failed = 0

                    for i in range(count):
                        pair = select_swap_pair()

                        print(Fore.YELLOW + Style.BRIGHT + f"\n{'='*70}")
                        print(Fore.YELLOW + Style.BRIGHT + f"WALLET {widx}/{total_wallets} - SWAP {i+1}/{count}: {pair['name']}")
                        print(Fore.YELLOW + Style.BRIGHT + f"{'='*70}")

                        receipt = bot.swap_tokens(pair['from'], pair['to'], Config.FIXED_SWAP_AMOUNT)

                        if receipt:
                            success += 1
                        else:
                            failed += 1

                        if i < count - 1:
                            log_info(f"Waiting {delay} seconds before next swap...\n")
                            time.sleep(delay)

                    overall_success += success
                    overall_failed += failed

                    log_info(f"Wallet {widx}/{total_wallets} completed: {success} success, {failed} failed")
                    # small pause between wallets
                    time.sleep(1)

            except Exception as e:
                log_error(f"Error during cycle {cycle}: {e}")
                import traceback
                traceback.print_exc()

            print(Fore.GREEN + Style.BRIGHT + f"\n{'='*70}")
            print(Fore.GREEN + Style.BRIGHT + f"=== CYCLE {cycle} COMPLETED ===")
            print(Fore.GREEN + Style.BRIGHT + f"{'='*70}")
            total_attempts = (overall_success + overall_failed)
            print(Fore.WHITE + f"Total swaps attempted: {total_attempts}")
            print(Fore.GREEN + f"Successful swaps: {overall_success}")
            print(Fore.RED + f"Failed swaps: {overall_failed}")
            rate = (overall_success/total_attempts*100) if total_attempts else 0
            print(Fore.WHITE + f"Success rate: {rate:.1f}%")
            print(Fore.GREEN + Style.BRIGHT + f"{'='*70}\n")

            # Wait 1.5 minutes before restarting the next cycle (non-blocking for exceptions)
            log_warn(f"Waiting 90 seconds (1.5 minutes) before next cycle...")
            for remaining in range(90, 0, -1):
                print(Fore.CYAN + f"  Next cycle in {remaining}s", end='\r', flush=True)
                time.sleep(1)
            print(Fore.CYAN + f"  Restarting...                    ")
        
    except KeyboardInterrupt:
        print(Fore.YELLOW + Style.BRIGHT + "\n\nStopped by user")
        sys.exit(0)
    except Exception as e:
        log_error(f"Critical error: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
