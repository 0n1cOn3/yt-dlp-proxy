import requests
import random
import os
import io
import time
import sys
import subprocess
import json

PROXIES_LIST_URL = "https://nnp.nnchan.ru/mahoproxy.php?u=https://api.sandvpn.com/fetch-free-proxys"
SPEEDTEST_URL = "http://212.183.159.230/5MB.zip"

def fetch_proxies():
    """Fetch the list of proxies from the defined URL."""
    try:
        response = requests.get(PROXIES_LIST_URL)
        response.raise_for_status()
        return response.json()
    except (requests.RequestException, json.JSONDecodeError) as e:
        print(f"Failed to fetch proxies: {e}")
        return []

def is_valid_proxy(proxy):
    """Check if the proxy is valid and not from Russia (youtube is slowed down there)."""
    return proxy["host"] and proxy["country"] != "Russia"

def construct_proxy_string(proxy):
    """Construct a proxy string from the proxy dictionary."""
    if proxy.get("username"):
        return f'{proxy["username"]}:{proxy["password"]}@{proxy["host"]}:{proxy["port"]}'
    return f'{proxy["host"]}:{proxy["port"]}'

def test_proxy(proxy):
    """Test the proxy by measuring the download time."""
    proxy_str = construct_proxy_string(proxy)
    print(f'Testing {proxy_str}')

    start_time = time.perf_counter()
    try:
        response = requests.get(SPEEDTEST_URL, stream=True, proxies={"http": proxy_str}, timeout=5)
        response.raise_for_status()

        total_length = response.headers.get('content-length')
        if total_length is None or int(total_length) != 5242880:
            print("No content or unexpected content size.")
            return None

        with io.BytesIO() as f:
            download_time, downloaded_bytes = download_with_progress(response, f, total_length, start_time)
            return {"time": download_time, **proxy}
    except requests.RequestException:
        print("Proxy is dead, skipping...")
        return None

def download_with_progress(response, f, total_length, start_time):
    """Download content with progress tracking."""
    downloaded_bytes = 0
    for chunk in response.iter_content(1024):
        downloaded_bytes += len(chunk)
        f.write(chunk)
        done = int(30 * downloaded_bytes / int(total_length))
        speed = downloaded_bytes / (time.perf_counter() - start_time) / 100000

        # Check if download speed is too low and skip if necessary
        if done > 3 and speed < 1.0:
            print("\nProxy is too slow, skipping...")
            return float('inf'), downloaded_bytes

        sys.stdout.write(f"\r[{'=' * done}{' ' * (30 - done)}] {speed:.2f} Mbps")
    sys.stdout.write("\n")
    return round(time.perf_counter() - start_time, 2), downloaded_bytes

def get_best_proxies(proxies):
    """Return the top five proxies based on speed."""
    proxy_times = [test_proxy(proxy) for proxy in proxies if is_valid_proxy(proxy)]
    return sorted(filter(None, proxy_times), key=lambda x: x['time'])[:5]

def save_proxies_to_file(proxies, filename="proxy.json"):
    """Save the best proxies to a JSON file."""
    try:
        with open(os.path.join(os.path.dirname(__file__), filename), "w") as f:
            json.dump(proxies, f, indent=4)
    except IOError as e:
        print(f"Failed to save proxies to file: {e}")

def update_proxies():
    """Update the proxies list and save the best ones."""
    proxies = fetch_proxies()
    best_proxies = get_best_proxies(proxies)
    save_proxies_to_file(best_proxies)
    print("All done.")

def run_yt_dlp():
    """Run yt-dlp with a randomly selected proxy."""
    while True:
        with open("proxy.json", "r") as f:
            proxies = json.load(f)
            if not proxies:
                print("No proxies available. Please run the update command first.")
                break

            proxy = random.choice(proxies)
            proxy_str = construct_proxy_string(proxy)
            print(f"Using proxy from {proxy['city']}, {proxy['country']}")

            if execute_yt_dlp_command(proxy_str):
                break  # Exit loop if command was successful
            print("Got 'Sign in to confirm' error. Trying again with another proxy...")
            time.sleep(1)  # Small delay before retrying

def execute_yt_dlp_command(proxy_str):
    """Execute the yt-dlp command with the given proxy."""
    command = f"yt-dlp --color always --proxy '{proxy_str}' {' '.join([str(arg) for arg in sys.argv])} 2>&1 | tee tempout"
    subprocess.run(command, shell=True)
    with open("tempout", 'r') as log_fl:
        result = 'Sign in to' not in log_fl.read()
    os.remove("tempout")  # Clean up after checking log file
    return result

def main():
    """Main function to handle script arguments and execute the appropriate command."""
    try:
        if "update" in sys.argv:
            update_proxies()
        elif len(sys.argv) < 2:
            print("usage: main.py update | <yt-dlp args> \nScript for starting yt-dlp with best free proxy\nCommands:\n update   Update best proxy")
        else:
            sys.argv.pop(0)
            run_yt_dlp()
    except KeyboardInterrupt:
        print("Canceled by user")

if __name__ == "__main__":
    main()
