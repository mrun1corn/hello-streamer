import re
import ssl
import json
import urllib.request
import urllib.error
import socket
from concurrent.futures import ThreadPoolExecutor, as_completed
import os

# Use default SSL verification to match browser behavior (blocks expired/invalid certificates)
ssl_context = ssl.create_default_context()

# Source priorities (lower is higher priority)
SOURCE_CHANNELS_JSON = 0
SOURCE_USER_PLAYLIST = 1
SOURCE_IPTV_ORG_BENGALI = 2
SOURCE_IPTV_ORG_SPORTS = 3
SOURCE_IPTV_ORG_BD = 4
SOURCE_IPTV_ORG_IN = 5
SOURCE_IPTV_ORG_MOVIES = 6
SOURCE_FREE_TV = 7
SOURCE_ANIK_BDIXI = 8

PLAYLIST_SOURCES = {
    "user_playlist": (SOURCE_USER_PLAYLIST, "https://github.com/abusaeeidx/Mrgify-BDIX-IPTV/raw/main/playlist.m3u"),
    "iptv_org_movies": (SOURCE_IPTV_ORG_MOVIES, "https://iptv-org.github.io/iptv/categories/movies.m3u"),
    "iptv_org_bengali": (SOURCE_IPTV_ORG_BENGALI, "https://iptv-org.github.io/iptv/languages/ben.m3u"),
    "iptv_org_sports": (SOURCE_IPTV_ORG_SPORTS, "https://iptv-org.github.io/iptv/categories/sports.m3u"),
    "iptv_org_bd": (SOURCE_IPTV_ORG_BD, "https://iptv-org.github.io/iptv/countries/bd.m3u"),
    "iptv_org_in": (SOURCE_IPTV_ORG_IN, "https://iptv-org.github.io/iptv/countries/in.m3u"),
    "free_tv": (SOURCE_FREE_TV, "https://raw.githubusercontent.com/Free-TV/IPTV/master/playlist.m3u8"),
    "anik_bdixi": (SOURCE_ANIK_BDIXI, "https://raw.githubusercontent.com/aniksarakash/IPTV/master/BDIXI_IPTV.m3u")
}

DEFAULT_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
    'Accept': '*/*',
    'Origin': 'https://hello-streamer.vercel.app',
    'Referer': 'https://hello-streamer.vercel.app/'
}

def load_existing_channels(json_path, js_path):
    """
    Loads existing channels from channels.json if available, or falls back to channels.js.
    """
    channels = []
    
    # 1. Try loading from channels.json
    if os.path.exists(json_path):
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if isinstance(data, list):
                    for item in data:
                        name = item.get("name", "").strip()
                        url = item.get("url", "").strip()
                        if name and url:
                            channels.append({
                                "name": name,
                                "url": url,
                                "logo": item.get("logo", "").strip(),
                                "group": item.get("group", "").strip(),
                                "backups": item.get("backups", []),
                                "source_priority": SOURCE_CHANNELS_JSON,
                                "source": "channels.json"
                            })
                            # Also include existing backups as candidate streams
                            for b_url in item.get("backups", []):
                                if b_url and b_url != url:
                                    channels.append({
                                        "name": name,
                                        "url": b_url.strip(),
                                        "logo": item.get("logo", "").strip(),
                                        "group": item.get("group", "").strip(),
                                        "backups": [],
                                        "source_priority": SOURCE_CHANNELS_JSON + 0.5,
                                        "source": "channels.json-backup"
                                    })
            print(f"Loaded {len(channels)} candidate entries from existing {json_path}")
            return channels
        except Exception as e:
            print(f"Error loading {json_path}: {e}")

    # 2. Fallback to channels.js parsing
    if os.path.exists(js_path):
        try:
            with open(js_path, 'r', encoding='utf-8') as f:
                content = f.read()

            match = re.search(r'const\s+CHANNELS\s*=\s*(\[.*?\])\s*;', content, re.DOTALL)
            if match:
                array_str = match.group(1)
                # Parse objects using regex that handles quotes and commas in fields accurately
                obj_matches = re.findall(r'\{\s*(.*?)\s*\}', array_str, re.DOTALL)
                for obj_str in obj_matches:
                    def get_field(field_name):
                        m = re.search(rf'{field_name}\s*:\s*["\'](.*?)["\'](?:\s*,|\s*$)', obj_str)
                        return m.group(1).strip() if m else ""

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
                            "backups": [],
                            "source_priority": SOURCE_CHANNELS_JSON,
                            "source": "channels.js"
                        })
            print(f"Parsed {len(channels)} channels from existing {js_path}")
        except Exception as e:
            print(f"Error parsing existing {js_path}: {e}")
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
            logo_match = re.search(r'tvg-logo=["\'](.*?)["\']', line)
            group_match = re.search(r'group-title=["\'](.*?)["\']', line)
            
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
                current_channel["backups"] = []
                current_channel["source_priority"] = priority
                current_channel["source"] = source_name
                if current_channel["name"] and current_channel["url"]:
                    channels.append(current_channel)
                current_channel = None
            else:
                url_name = line.split('/')[-1].split('.')[0]
                channels.append({
                    "name": url_name,
                    "url": line,
                    "logo": "",
                    "group": "",
                    "backups": [],
                    "source_priority": priority,
                    "source": source_name
                })
    return channels

def normalize_name(name):
    """
    Normalizes channel names to facilitate deduplication.
    """
    n = name.lower().strip()
    # Remove bracketed content like (backup), [SD], (720p), etc.
    n = re.sub(r'[\(\[\{].*?[\)\]\}]', '', n)
    # Remove common suffixes/qualifiers
    n = re.sub(r'\b(hd|sd|fhd|uhd|4k|tv|live|bd|stream|temporary|backup|online|asia|india|uk|usa|bangla|not\s+24\/7|geo-blocked)\b', '', n)
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

    # Movies
    if any(x in name for x in ["movie", "movies", "cinema", "cineplex", "film", "films", "hollywood", "bollywood", "goldmines", "filamchi", "b4u movies", "star gold", "sony max", "zee cinema", "colors cineplex", "shemaroo movies", "dangal movies", "manoranjan movies", "cineworld", "filmrise", "cinevault", "moviesphere", "pluto tv movies"]):
        return "Movies"
    if any(x in sg for x in ["movie", "movies", "cinema", "cineplex", "film", "films"]):
        return "Movies"

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

def probe_url(url, timeout=4):
    """
    Probes a specific URL for valid HLS/media content.
    Returns (is_working, error_msg, final_url)
    """
    try:
        req = urllib.request.Request(url, headers=DEFAULT_HEADERS)
        with urllib.request.urlopen(req, timeout=timeout, context=ssl_context) as response:
            code = response.getcode()
            if code != 200:
                return False, f"HTTP {code}", url
            
            # Read first 2048 bytes to inspect header
            head = response.read(2048)
            if not head:
                return False, "Empty Response", url

            # Check for HTML error pages (soft-200)
            head_lower = head[:500].lower()
            if b"<!doctype html" in head_lower or b"<html" in head_lower or b"<head" in head_lower:
                return False, "Invalid Payload (HTML Error Page)", url

            # Valid HLS manifest
            if b"#EXTM3U" in head:
                return True, "OK (HLS)", url

            # Valid MPEG-TS binary stream (0x47 sync byte)
            if len(head) >= 188 and head[0] == 0x47:
                return True, "OK (TS)", url

            # Other media stream formats
            if b"ftyp" in head or b"moov" in head or b"OggS" in head:
                return True, "OK (Media)", url

            # Fallback check for text manifests without strict #EXTM3U at byte 0
            if b"#EXTINF" in head or b"#EXT-X-" in head:
                return True, "OK (HLS Chunk)", url

            return False, "Unrecognized Stream Format", url
    except urllib.error.HTTPError as e:
        return False, f"HTTP {e.code}", url
    except urllib.error.URLError as e:
        return False, f"URL Error: {e.reason}", url
    except socket.timeout:
        return False, "Timeout", url
    except Exception as e:
        return False, f"Error: {str(e)}", url

def check_stream(channel, timeout=4, https_only=True):
    """
    Checks if a channel stream URL is working.
    Attempts HTTPS upgrade automatically if the stream is HTTP.
    Enforces HTTPS-only compliance to prevent browser mixed-content errors on HTTPS hosts.
    Returns (channel, is_working, error_message)
    """
    original_url = channel["url"]
    
    # 1. If URL is HTTP, try upgrading to HTTPS first
    if original_url.startswith("http://"):
        https_url = "https://" + original_url[7:]
        ok, msg, final_url = probe_url(https_url, timeout=timeout)
        if ok:
            channel_copy = dict(channel)
            channel_copy["url"] = final_url
            return channel_copy, True, "OK (Upgraded to HTTPS)"
        if https_only:
            return channel, False, "Insecure HTTP stream (failed HTTPS upgrade)"
    
    # 2. Probe the configured HTTPS URL
    if not original_url.startswith("https://") and https_only:
        return channel, False, "Insecure HTTP stream"

    ok, msg, final_url = probe_url(original_url, timeout=timeout)
    if ok:
        channel_copy = dict(channel)
        channel_copy["url"] = final_url
        return channel_copy, True, msg
    
    return channel, False, msg
def main():
    workspace_dir = os.path.dirname(os.path.abspath(__file__))
    channels_json_path = os.path.join(workspace_dir, "channels.json")
    channels_js_path = os.path.join(workspace_dir, "channels.js")

    print("=========================================")
    print("      IPTV STREAM CHECKER & DEDUPLICATOR ")
    print("=========================================")

    # 1. Gather existing channels from channels.json / channels.js
    candidate_channels = load_existing_channels(channels_json_path, channels_js_path)

    # 2. Gather channels from remote playlists
    for name, (priority, url) in PLAYLIST_SOURCES.items():
        print(f"Fetching remote playlist: {name}...")
        try:
            req = urllib.request.Request(url, headers=DEFAULT_HEADERS)
            with urllib.request.urlopen(req, timeout=10, context=ssl_context) as response:
                content = response.read().decode('utf-8', errors='ignore')
            
            playlist_channels = parse_m3u(content, name, priority)
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

    # Deduplicate candidate list strictly by URL before checking
    unique_url_candidates = []
    seen_urls = set()
    for c in candidate_channels:
        url = c["url"].strip()
        if url and url not in seen_urls:
            seen_urls.add(url)
            unique_url_candidates.append(c)
    
    print(f"Deduplicated to {len(unique_url_candidates)} unique URLs (removed {total_candidates - len(unique_url_candidates)} duplicate URLs)")

    # 3. Check streams in parallel
    working_channels = []
    broken_count = 0
    checked_count = 0

    print("\nValidating streams in parallel with deep manifest inspection (80 workers)...")
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

    # 4. Multi-Stream Deduplication & Backup Collection by Normalized Name
    final_channels = {}
    
    for c in working_channels:
        norm_name = normalize_name(c["name"])
        if not norm_name:
            continue
        
        c["group"] = categorize(c["name"], c["group"])
        url = c["url"].strip()

        if norm_name in final_channels:
            existing = final_channels[norm_name]
            
            # If candidate has higher priority, make it primary and push existing into backups
            if c["source_priority"] < existing["source_priority"]:
                # Old primary becomes backup if different URL
                if existing["url"] not in c.get("backups", []) and existing["url"] != url:
                    c.setdefault("backups", []).append(existing["url"])
                # Inherit any existing backups
                for b_url in existing.get("backups", []):
                    if b_url != url and b_url not in c["backups"] and len(c["backups"]) < 3:
                        c["backups"].append(b_url)
                final_channels[norm_name] = c
            else:
                # Add candidate URL to existing channel's backups if unique (up to 3 backups)
                existing.setdefault("backups", [])
                if url != existing["url"] and url not in existing["backups"] and len(existing["backups"]) < 3:
                    existing["backups"].append(url)
        else:
            c.setdefault("backups", [])
            final_channels[norm_name] = c

    deduped_channels = list(final_channels.values())
    total_backups = sum(len(c.get("backups", [])) for c in deduped_channels)
    print(f"Deduplication complete: {len(deduped_channels)} channels retained with {total_backups} total backup failover streams.")

    # 5. Sort channels logically by group and alphabetically
    group_order = ["Movies", "Bangladesh", "Sports", "Indian Bangla", "Indian", "News", "International", "Religious", "Kids", "Music"]
    
    def get_sort_key(c):
        g = c["group"]
        g_idx = group_order.index(g) if g in group_order else len(group_order)
        return (g_idx, c["name"].lower())

    deduped_channels.sort(key=get_sort_key)

    # Re-assign IDs and sanitize fields
    clean_channels = []
    for idx, c in enumerate(deduped_channels):
        clean_channels.append({
            "id": idx + 1,
            "name": c["name"].strip(),
            "group": c["group"].strip(),
            "logo": c.get("logo", "").strip(),
            "url": c["url"].strip(),
            "backups": [b.strip() for b in c.get("backups", []) if b.strip() and b.strip() != c["url"].strip()]
        })

    # 6. Save channels.json (Primary Modern Store)
    try:
        with open(channels_json_path, "w", encoding="utf-8") as f:
            json.dump(clean_channels, f, indent=2, ensure_ascii=False)
        print(f"\n[OK] Saved {len(clean_channels)} channels to {channels_json_path}")
    except Exception as e:
        print(f"Error saving to channels.json: {e}")

    # 7. Save channels.js (Backwards Compatible Store)
    js_content = "window.CHANNELS = [\n"
    last_group = None
    
    for c in clean_channels:
        if c["group"] != last_group:
            last_group = c["group"]
            js_content += f"\n  // ── {last_group.upper()} " + "─"*(42 - len(last_group)) + "\n"

        name_esc = c["name"].replace('\\', '\\\\').replace('"', '\\"')
        group_esc = c["group"].replace('\\', '\\\\').replace('"', '\\"')
        logo_esc = c["logo"].replace('\\', '\\\\').replace('"', '\\"')
        url_esc = c["url"].replace('\\', '\\\\').replace('"', '\\"')
        backups_json = json.dumps(c["backups"])

        js_content += f'  {{ id:{c["id"]:<3}, name:"{name_esc}", group:"{group_esc}", logo:"{logo_esc}", url:"{url_esc}", backups:{backups_json} }},\n'

    js_content += "window.GROUPS = ['All', ...new Set(window.CHANNELS.map(c => c.group))];\n"

    try:
        with open(channels_js_path, "w", encoding="utf-8") as f:
            f.write(js_content)
        print(f"[OK] Saved {len(clean_channels)} channels to {channels_js_path}")
    except Exception as e:
        print(f"Error saving to channels.js: {e}")

    # Print breakdown by group
    group_counts = {}
    for c in clean_channels:
        group_counts[c["group"]] = group_counts.get(c["group"], 0) + 1
    
    print("\nChannel breakdown by group:")
    for group in group_order:
        if group in group_counts:
            print(f" - {group}: {group_counts[group]} channels")

    print("\nRun complete.")

if __name__ == "__main__":
    main()
