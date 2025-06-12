import json
from datetime import datetime
import os

# Initialize KV as None first
kv = None

# Get Vercel KV credentials from environment variables
kv_url = os.getenv('KV_REST_API_URL')
kv_token = os.getenv('KV_REST_API_TOKEN')

if kv_url and kv_token:
    try:
        # Attempt 1: Standard synchronous client (most appropriate for Flask)
        from vercel_kv.sync import KV
        kv = KV(url=kv_url, token=kv_token)
        print("Successfully initialized Vercel KV using vercel_kv.sync.KV")
    except (ImportError, AttributeError, Exception) as e_sync:
        print(f"Failed to initialize Vercel KV with vercel_kv.sync.KV: {e_sync}")
        print("Attempting fallback: from vercel_kv import KV")
        try:
            # Attempt 2: Base KV class (could be async, or from a simplified/local vercel_kv.py)
            # The error message "Did you mean: 'KV'?" suggests this might be available.
            from vercel_kv import KV as VercelKV # Use an alias to avoid potential name conflicts
            kv = VercelKV(url=kv_url, token=kv_token)
            print("Successfully initialized Vercel KV using vercel_kv.KV.")
            # Add a warning if this client might be async and the code expects sync
            # For now, assume it's usable if found.
        except (ImportError, AttributeError, Exception) as e_base:
            print(f"Failed to initialize Vercel KV with vercel_kv.KV: {e_base}")
            kv = None # Ensure kv is None if all attempts fail
else:
    print("Warning: Vercel KV environment variables (KV_REST_API_URL, KV_REST_API_TOKEN) are not set.")
    # kv is already None if initialized as such at the top, but being explicit is fine.
    kv = None 

if kv is None:
    print("Warning: Vercel KV not available, using fallback storage.")


class LetterManager:
    def __init__(self, kv_key='letters_data_store'):
        self.kv_key = kv_key
        # Ensure data is loaded after kv is potentially initialized
        self.data = self.load_data()
    
    def load_data(self):
        """Load data from Vercel KV or create empty structure"""
        if not kv: # Check if kv was successfully initialized
            print("KV client not available, loading from file.")
            return self.load_from_file()
        
        try:
            raw_data = kv.get(self.kv_key)
            if raw_data:
                try:
                    # Vercel KV often stores JSON as strings
                    return json.loads(raw_data) if isinstance(raw_data, str) else raw_data
                except (json.JSONDecodeError, TypeError) as e:
                    print(f"Warning: Invalid JSON in KV store ('{self.kv_key}'). Error: {e}. Raw data: '{raw_data}'. Using empty structure.")
                    return {"penpals": {}}
            return {"penpals": {}} # No data found or raw_data is None/empty
        except Exception as e:
            print(f"Error loading from KV ('{self.kv_key}'): {e}. Falling back to file.")
            return self.load_from_file()

    def load_from_file(self):
        """Fallback file-based storage"""
        file_path = 'letters_data.json'
        try:
            if os.path.exists(file_path):
                with open(file_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            else:
                print(f"Fallback file '{file_path}' not found. Starting with empty data.")
        except Exception as e:
            print(f"Error loading from file '{file_path}': {e}")
        return {"penpals": {}}
    
    def save_data(self):
        """Save data to Vercel KV or file"""
        if kv: # Check if kv was successfully initialized
            try:
                # Ensure data is JSON serializable string
                json_data = json.dumps(self.data)
                kv.set(self.kv_key, json_data)
                print(f"Data saved to Vercel KV key '{self.kv_key}'.")
                return True
            except Exception as e:
                print(f"Error saving to KV ('{self.kv_key}'): {e}. Attempting file save.")
                # Fall through to file save if KV save fails
        
        # Fallback to file storage
        file_path = 'letters_data.json'
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, indent=2, ensure_ascii=False)
            print(f"Data saved to fallback file '{file_path}'.")
            return True
        except Exception as e:
            print(f"Error saving to file '{file_path}': {e}")
            return False
    
    def add_penpal(self, name, country):
        """Add a new penpal"""
        if name not in self.data["penpals"]:
            self.data["penpals"][name] = {
                "country": country,
                "letters": [],
                "notes": [],
                "created_date": datetime.now().isoformat()
            }
            self.save_data()
            return True
        return False
    
    def add_letter(self, penpal_name, content, date_received=None):
        """Add a letter from a penpal"""
        if penpal_name in self.data["penpals"]:
            if date_received is None:
                date_received = datetime.now().isoformat()
            
            letter = {
                "content": content,
                "date_received": date_received,
                "date_added": datetime.now().isoformat()
            }
            
            self.data["penpals"][penpal_name]["letters"].append(letter)
            self.save_data()
            return True
        return False
    
    def add_note(self, penpal_name, note):
        """Add a note about a penpal"""
        if penpal_name in self.data["penpals"]:
            note_data = {
                "note": note,
                "date_added": datetime.now().isoformat()
            }
            self.data["penpals"][penpal_name]["notes"].append(note_data)
            self.save_data()
            return True
        return False
    
    def delete_note(self, penpal_name, note_index):
        """Delete a note about a penpal"""
        if (penpal_name in self.data["penpals"] and 
            0 <= note_index < len(self.data["penpals"][penpal_name]["notes"])):
            del self.data["penpals"][penpal_name]["notes"][note_index]
            self.save_data()
            return True
        return False
    
    def get_penpal(self, name):
        """Get penpal data"""
        return self.data["penpals"].get(name)
    
    def get_all_penpals(self):
        """Get all penpals with summary info"""
        penpals = []
        for name, data in self.data["penpals"].items():
            penpal_info = {
                "name": name,
                "country": data["country"],
                "letter_count": len(data["letters"]),
                "note_count": len(data["notes"]),
                "last_letter": None
            }
            
            if data["letters"]:
                last_letter = max(data["letters"], key=lambda x: x["date_received"])
                penpal_info["last_letter"] = last_letter["date_received"]
            
            penpals.append(penpal_info)
        
        # Sort by last letter date (most recent first)
        penpals.sort(key=lambda x: x["last_letter"] or "0000-00-00", reverse=True)
        return penpals
    
    def search_letters(self, query):
        """Search letters by content"""
        results = []
        query_lower = query.lower()
        
        for penpal_name, penpal_data in self.data["penpals"].items():
            for letter in penpal_data["letters"]:
                if query_lower in letter["content"].lower():
                    results.append({
                        "penpal_name": penpal_name,
                        "country": penpal_data["country"],
                        "letter": letter,
                        "preview": self.get_preview(letter["content"], query, 200)
                    })
        
        return results
    
    def get_preview(self, text, query, max_length=200):
        """Get a preview of text around the search query"""
        query_lower = query.lower()
        text_lower = text.lower()
        
        if query_lower not in text_lower:
            return text[:max_length] + "..." if len(text) > max_length else text
        
        # Find the position of the query
        pos = text_lower.find(query_lower)
        start = max(0, pos - max_length // 2)
        end = min(len(text), start + max_length)
        
        preview = text[start:end]
        if start > 0:
            preview = "..." + preview
        if end < len(text):
            preview = preview + "..."
        
        return preview
    
    def get_stats(self):
        """Get statistics about the letters"""
        total_penpals = len(self.data["penpals"])
        total_letters = sum(len(penpal["letters"]) for penpal in self.data["penpals"].values())
        countries = set(penpal["country"] for penpal in self.data["penpals"].values())
        
        return {
            "total_penpals": total_penpals,
            "total_letters": total_letters,
            "countries": len(countries),
            "country_list": sorted(list(countries))
        }
