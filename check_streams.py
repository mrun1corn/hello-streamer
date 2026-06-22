import re
import ssl
import urllib.request
import urllib.error
import socket
from concurrent.futures import ThreadPoolExecutor, as_completed
import os

# Use default SSL verification to match browser behavior (blocks expired/invalid certificates)
ssl_context = ssl.create_default_context()

# Source priorities (lower is higher priority)
SOURCE_CHANNELS_JS = 0
SOURCE_USER_PLAYLIST = 1
SOURCE_IPTV_ORG_BD = 2
SOURCE_IPTV_ORG_IN = 3
SOURCE_LUPAEL_RUNNING = 4
SOURCE_LUPAEL_PLAY = 5
SOURCE_LUPAEL_WORLD = 6
SOURCE_ANIK_BDIXI = 7

PLAYLIST_SOURCES = {
    "user_playlist": (SOURCE_USER_PLAYLIST, "https://github.com/abusaeeidx/Mrgify-BDIX-IPTV/raw/main/playlist.m3u"),
    "iptv_org_bd": (SOURCE_IPTV_ORG_BD, "https://iptv-org.github.io/iptv/countries/bd.m3u"),
    "iptv_org_in": (SOURCE_IPTV_ORG_IN, "https://iptv-org.github.io/iptv/countries/in.m3u"),
    "lupael_running": (SOURCE_LUPAEL_RUNNING, "https://raw.githubusercontent.com/lupael/IPTV/master/running.m3u"),
    "lupael_play": (SOURCE_LUPAEL_PLAY, "https://raw.githubusercontent.com/lupael/IPTV/master/play.m3u"),
    "lupael_world": (SOURCE_LUPAEL_WORLD, "https://raw.githubusercontent.com/lupael/IPTV/master/world.m3u"),
    "anik_bdixi": (SOURCE_ANIK_BDIXI, "https://raw.githubusercontent.com/aniksarakash/IPTV/master/BDIXI_IPTV.m3u")
}

def parse_existing_channels_js(filepath):
    """
    Parses channels.js and extracts existing channels.
    """
    channels = []
    if not os.path.exists(filepath):
        print(f"channels.js not found at {filepath}. Starting with empty list.")
        return channels

    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()

        # Find array contents
        match = re.search(r'const\s+CHANNELS\s*=\s*\[(.*?)\]\s*;', content, re.DOTALL)
        if not match:
            return channels

        array_content = match.group(1)
        obj_matches = re.findall(r'\{\s*(.*?)\s*\}', array_content, re.DOTALL)

        for obj_str in obj_matches:
            def get_field(field_name):
                # Matches: key: "value" or key:'value' or key: `value`
                f_match = re.search(rf'{field_name}\s*:\s*["\'`]?([^"\'`\n,]+)["\'`]?', obj_str)
                return f_match.group(1).strip() if f_match else ""

            name = get_field("name")
            url = get_field("url")
            logo = get_field("logo")
            group = get_field("group")

            if name and url:
                channels.append({
                    "name": name,
                    "url": url,
                    "logo": logo,
                    "group": group,
                    "source_priority": SOURCE_CHANNELS_JS,
                    "source": "channels.js"
                })
        print(f"Parsed {len(channels)} channels from existing channels.js")
    except Exception as e:
        print(f"Error parsing existing channels.js: {e}")
    return channels

def parse_m3u(m3u_content, source_name, priority):
    """
    Parses M3U file content and returns list of channel dictionaries.
    """
    channels = []
    lines = m3u_content.splitlines()
    current_channel = None

    for line in lines:
        line = line.strip()
        if not line:
            continue
        if line.startswith("#EXTINF"):
            current_channel = {}
            # Try to extract tvg-logo
            logo_match = re.search(r'tvg-logo=["\'](.*?)["\']', line)
            # Try to extract group-title
            group_match = re.search(r'group-title=["\'](.*?)["\']', line)
            
            # The channel name is after the last comma
            comma_idx = line.rfind(',')
            name = line[comma_idx+1:].strip() if comma_idx != -1 else ""

            current_channel["name"] = name
            current_channel["logo"] = logo_match.group(1).strip() if logo_match else ""
            current_channel["group"] = group_match.group(1).strip() if group_match else ""
        elif line.startswith("#"):
            continue
        else:
            if current_channel is not None:
                current_channel["url"] = line
                current_channel["source_priority"] = priority
                current_channel["source"] = source_name
                if current_channel["name"] and current_channel["url"]:
                    channels.append(current_channel)
                current_channel = None
            else:
                # URL alone
                url_name = line.split('/')[-1].split('.')[0]
                channels.append({
                    "name": url_name,
                    "url": line,
                    "logo": "",
                    "group": "",
                    "source_priority": priority,
                    "source": source_name
                })
    return channels

def normalize_name(name):
    """
    Normalizes channel names to facilitate deduplication.
    """
    n = name.lower().strip()
    # Remove bracketed content like (backup), [SD], etc.
    n = re.sub(r'[\(\[\{].*?[\)\]\}]', '', n)
    # Remove common suffixes/words
    n = re.sub(r'\b(hd|sd|fhd|uhd|4k|tv|live|bd|stream|temporary|backup|online|asia|india|uk|usa|bangla)\b', '', n)
    # Keep alphanumeric and whitespace
    n = re.sub(r'[^a-z0-9\s]', '', n)
    # Collapse whitespace
    n = " ".join(n.split())
    return n

def categorize(channel_name, source_group):
    """
    Categorizes channels into fixed web groups.
    """
    name = channel_name.lower()
    sg = source_group.lower() if source_group else ""

    # Sports
    if any(x in name for x in ["sports", "cricket", "willow", "bein", "football", "espn", "eurosport", "ten 1", "ten 2", "ten 3", "sony six", "sony ten", "t sports", "t-sports", "gtv", "gazi"]):
        return "Sports"
    if any(x in sg for x in ["sports", "sport", "cricket", "football"]):
        return "Sports"

    # Kids
    if any(x in name for x in ["kids", "cartoon", "jungle book", "pbs kids", "pogo", "nickelodeon", "disney", "rongeen", "duronto"]):
        return "Kids"
    if any(x in sg for x in ["kids", "kid", "cartoon", "cartoons"]):
        return "Kids"

    # Religious
    if any(x in name for x in ["peace tv", "quran", "sunnah", "islam", "makkah", "madina", "religious", "bible", "saudi quran"]):
        return "Religious"
    if any(x in sg for x in ["religious", "religion", "islamic", "islam"]):
        return "Religious"

    # News
    if any(x in name for x in ["news", "al jazeera", "bbc", "cnn", "dw", "rt ", "cna", "bloomberg", "somoy", "independent", "ekattor", "channel 24", "jamuna", "abp ananda", "zee 24 ghanta", "r plus news", "atn news"]):
        return "News"
    if any(x in sg for x in ["news", "information"]):
        return "News"

    # Music
    if any(x in name for x in ["music", "beats", "9xm", "9x jalwa", "8xm", "music bangla"]):
        return "Music"
    if any(x in sg for x in ["music", "song", "songs"]):
        return "Music"

    # Indian Bangla
    if any(x in name for x in ["jalsha", "zee bangla", "sony aath", "colors bangla", "ruposhi", "aakash aath", "star jalsha", "dd bangla"]):
        return "Indian Bangla"
    if "bangla" in name and any(x in name for x in ["zee", "star", "colors", "sony", "dd", "etv"]):
        return "Indian Bangla"
    if any(x in sg for x in ["indian bangla", "west bengal", "bangla india", "bengali"]):
        return "Indian Bangla"

    # Indian
    if any(x in name for x in ["ndtv", "zee", "sony", "colors", "star gold", "star plus", "star bharat", "star movies", "star world", "dangal", "shemaroo", "rishtey", "anmol", "big magic", "dabaang", "dd national", "dd india", "dd retro", "dd bharati", "sun tv", "etv", "vijay", "asianet", "sab tv", "bindass", "zoom"]):
        return "Indian"
    if any(x in sg for x in ["india", "hindi", "ind.", "ind ", "tamil", "telugu", "malayalam", "kannada", "punjabi", "marathi", "bhojpuri", "gujarati", "urdu"]):
        return "Indian"

    # Bangladesh
    if any(x in name for x in ["bangla", "btv", "ntv", "channel i", "atn bangla", "banglavision", "deepto", "rtv", "maasranga", "asian tv", "ekhone", "deshi", "desh tv"]):
        return "Bangladesh"
    if any(x in sg for x in ["bangladesh", "bangla", "akash go", "bdix"]):
        return "Bangladesh"

    # International
    if any(x in name for x in ["abc", "france 24", "euronews", "nasa", "accuweather", "bloomberg", "dw"]):
        return "International"
    if "international" in sg or "english" in sg or "world" in sg:
        return "International"

    return "International"
def check_stream(channel, timeout=3):
    """
    Checks if a stream URL is working.
    Returns (channel, is_working, error_message)
    """
    url = channel["url"]
    try:
        req = urllib.request.Request(
            url,
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            }
        )
        with urllib.request.urlopen(req, timeout=timeout, context=ssl_context) as response:
            code = response.getcode()
            if code == 200:
                # Read first 1024 bytes to check for real stream contents (HLS headers or binary TS data)
                head = response.read(1024)
                if len(head) > 0:
                    return channel, True, "OK"
                else:
                    return channel, False, "Empty Response"
            else:
                return channel, False, f"HTTP {code}"
    except urllib.error.HTTPError as e:
        return channel, False, f"HTTP {e.code}"
    except urllib.error.URLError as e:
        return channel, False, f"URL Error: {e.reason}"
    except socket.timeout:
        return channel, False, "Timeout"
    except Exception as e:
        return channel, False, f"Error: {str(e)}"

def main():
    workspace_dir = os.path.dirname(os.path.abspath(__file__))
    channels_js_path = os.path.join(workspace_dir, "channels.js")

    print("=========================================")
    print("      IPTV STREAM CHECKER & DEDUPLICATOR ")
    print("=========================================")

    # 1. Gather existing channels from channels.js
    candidate_channels = parse_existing_channels_js(channels_js_path)

    # 2. Gather channels from remote playlists
    for name, (priority, url) in PLAYLIST_SOURCES.items():
        print(f"Fetching remote playlist: {name}...")
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=10, context=ssl_context) as response:
                content = response.read().decode('utf-8', errors='ignore')
            
            playlist_channels = parse_m3u(content, name, priority)
            # Filter out channels categorized as "International" from remote playlists
            # to focus on the target categories (BD, Indian, Sports, News, etc.)
            filtered_channels = []
            for c in playlist_channels:
                grp = categorize(c["name"], c["group"])
                if grp != "International":
                    filtered_channels.append(c)
            candidate_channels.extend(filtered_channels)
            print(f"Parsed {len(playlist_channels)} channels from {name} (filtered to {len(filtered_channels)} target channels)")
        except Exception as e:
            print(f"Error fetching {name}: {e}")
    total_candidates = len(candidate_channels)
    print(f"\nTotal candidate channels to check: {total_candidates}")

    # Deduplicate candidate list strictly by URL before checking to avoid wasting time testing identical streams
    unique_url_candidates = []
    seen_urls = set()
    for c in candidate_channels:
        url = c["url"].strip()
        if url not in seen_urls:
            seen_urls.add(url)
            unique_url_candidates.append(c)
    
    print(f"Deduplicated to {len(unique_url_candidates)} unique URLs (removed {total_candidates - len(unique_url_candidates)} duplicate URLs)")

    # 3. Check streams in parallel
    working_channels = []
    broken_count = 0
    checked_count = 0

    print("\nValidating streams in parallel (this may take a minute)...")
    with ThreadPoolExecutor(max_workers=80) as executor:
        futures = [executor.submit(check_stream, c) for c in unique_url_candidates]
        
        for future in as_completed(futures):
            channel, is_working, msg = future.result()
            checked_count += 1
            if is_working:
                working_channels.append(channel)
            else:
                broken_count += 1
            
            if checked_count % 50 == 0 or checked_count == len(unique_url_candidates):
                print(f"Progress: {checked_count}/{len(unique_url_candidates)} checked ({len(working_channels)} working, {broken_count} offline)")

    print(f"\nStream checking complete. Found {len(working_channels)} working streams and {broken_count} broken/offline streams.")

    # 4. Strict Deduplication by Normalized Channel Name
    # We want exactly one working stream per channel name.
    # We prioritize the source: channels.js (0) > user_playlist (1) > iptv_org_bd (2) > iptv_org_in (3)
    final_channels = {}
    duplicate_name_count = 0

    for c in working_channels:
        norm_name = normalize_name(c["name"])
        if not norm_name:
            continue
        
        # Categorize the channel into our official groups
        c["group"] = categorize(c["name"], c["group"])

        # Deduplication choice logic
        if norm_name in final_channels:
            existing = final_channels[norm_name]
            # Replace if new one has higher priority (lower value is higher priority)
            # or if they have same priority but the new name matches the normalized representation better
            if c["source_priority"] < existing["source_priority"]:
                final_channels[norm_name] = c
                duplicate_name_count += 1
            else:
                duplicate_name_count += 1
        else:
            final_channels[norm_name] = c

    deduped_channels = list(final_channels.values())
    print(f"Name deduplication complete. Kept {len(deduped_channels)} channels (filtered out {duplicate_name_count} duplicates/backups).")

    # 5. Output and format channels.js
    # Sort groups logically, and channels alphabetically within groups
    group_order = ["Bangladesh", "Sports", "Indian Bangla", "Indian", "News", "International", "Religious", "Kids", "Music"]
    
    def get_sort_key(c):
        g = c["group"]
        g_idx = group_order.index(g) if g in group_order else len(group_order)
        return (g_idx, c["name"].lower())

    deduped_channels.sort(key=get_sort_key)

    # Re-assign IDs
    for idx, c in enumerate(deduped_channels):
        c["id"] = idx + 1

    # Format channels.js content beautifully
    js_content = "const CHANNELS = [\n"
    last_group = None
    
    for c in deduped_channels:
        if c["group"] != last_group:
            last_group = c["group"]
            js_content += f"\n  // ── {last_group.upper()} " + "─"*(42 - len(last_group)) + "\n"

        name_esc = c["name"].replace('"', '\\"')
        group_esc = c["group"].replace('"', '\\"')
        logo_esc = c["logo"].replace('"', '\\"')
        url_esc = c["url"].replace('"', '\\"')

        js_content += f'  {{ id:{c["id"]:<3}, name:"{name_esc}", group:"{group_esc}", logo:"{logo_esc}", url:"{url_esc}" }},\n'

    js_content += "];\n\n"
    js_content += "const GROUPS = ['All', ...new Set(CHANNELS.map(c => c.group))];\n"

    try:
        with open(channels_js_path, "w", encoding="utf-8") as f:
            f.write(js_content)
        print(f"\nSuccess! Saved {len(deduped_channels)} working, deduplicated channels into channels.js")
    except Exception as e:
        print(f"Error saving to channels.js: {e}")

    # Print breakdown by group
    group_counts = {}
    for c in deduped_channels:
        group_counts[c["group"]] = group_counts.get(c["group"], 0) + 1
    
    print("\nChannel breakdown by group:")
    for group in group_order:
        if group in group_counts:
            print(f" - {group}: {group_counts[group]} channels")

    print("\nRun complete. Have a great day!")

if __name__ == "__main__":
    main()
