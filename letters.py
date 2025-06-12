import json
import psycopg2
from datetime import datetime
import os
from urllib.parse import urlparse

class LetterManager:
    def __init__(self):
        self.db_url = os.getenv('POSTGRES_URL')
        self.use_postgres = bool(self.db_url)
        self.init_database()
        print(f"LetterManager initialized with {'Postgres' if self.use_postgres else 'file'} storage")
    
    def get_connection(self):
        """Get database connection"""
        if not self.use_postgres:
            return None
        
        try:
            # Parse the database URL
            parsed = urlparse(self.db_url)
            conn = psycopg2.connect(
                host=parsed.hostname,
                port=parsed.port,
                database=parsed.path[1:],  # Remove leading slash
                user=parsed.username,
                password=parsed.password,
                sslmode='require'
            )
            return conn
        except Exception as e:
            print(f"Database connection error: {e}")
            return None
    
    def init_database(self):
        """Initialize database tables"""
        if not self.use_postgres:
            return
        
        conn = self.get_connection()
        if not conn:
            return
        
        try:
            cur = conn.cursor()
            
            # Create penpals table
            cur.execute('''
                CREATE TABLE IF NOT EXISTS penpals (
                    id SERIAL PRIMARY KEY,
                    name VARCHAR(255) UNIQUE NOT NULL,
                    country VARCHAR(255) NOT NULL,
                    created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Create letters table
            cur.execute('''
                CREATE TABLE IF NOT EXISTS letters (
                    id SERIAL PRIMARY KEY,
                    penpal_id INTEGER REFERENCES penpals(id) ON DELETE CASCADE,
                    content TEXT NOT NULL,
                    date_received TIMESTAMP NOT NULL,
                    date_added TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Create notes table
            cur.execute('''
                CREATE TABLE IF NOT EXISTS notes (
                    id SERIAL PRIMARY KEY,
                    penpal_id INTEGER REFERENCES penpals(id) ON DELETE CASCADE,
                    note TEXT NOT NULL,
                    date_added TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            conn.commit()
            print("Database tables initialized successfully")
            
        except Exception as e:
            print(f"Error initializing database: {e}")
            conn.rollback()
        finally:
            cur.close()
            conn.close()
    
    def add_penpal(self, name, country):
        """Add a new penpal"""
        if not self.use_postgres:
            return self.add_penpal_file(name, country)
        
        conn = self.get_connection()
        if not conn:
            return False
        
        try:
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO penpals (name, country) VALUES (%s, %s)",
                (name, country)
            )
            conn.commit()
            print(f"Added penpal {name} from {country}")
            return True
            
        except psycopg2.IntegrityError:
            print(f"Penpal {name} already exists")
            conn.rollback()
            return False
        except Exception as e:
            print(f"Error adding penpal: {e}")
            conn.rollback()
            return False
        finally:
            cur.close()
            conn.close()
    
    def add_letter(self, penpal_name, content, date_received=None):
        """Add a letter from a penpal"""
        if not self.use_postgres:
            return self.add_letter_file(penpal_name, content, date_received)
        
        if date_received is None:
            date_received = datetime.now()
        elif isinstance(date_received, str):
            date_received = datetime.fromisoformat(date_received.replace('Z', '+00:00'))
        
        conn = self.get_connection()
        if not conn:
            return False
        
        try:
            cur = conn.cursor()
            
            # Get penpal ID
            cur.execute("SELECT id FROM penpals WHERE name = %s", (penpal_name,))
            result = cur.fetchone()
            if not result:
                print(f"Penpal {penpal_name} not found")
                return False
            
            penpal_id = result[0]
            
            # Add letter
            cur.execute(
                "INSERT INTO letters (penpal_id, content, date_received) VALUES (%s, %s, %s)",
                (penpal_id, content, date_received)
            )
            conn.commit()
            print(f"Added letter for {penpal_name}")
            return True
            
        except Exception as e:
            print(f"Error adding letter: {e}")
            conn.rollback()
            return False
        finally:
            cur.close()
            conn.close()
            
    def delete_letter_file(self, penpal_name, letter_index):
        data = self.load_from_file()
        if (penpal_name in data["penpals"] and 
            0 <= letter_index < len(data["penpals"][penpal_name]["letters"])):
            del data["penpals"][penpal_name]["letters"][letter_index]
            return self.save_to_file(data)
        return False

    def delete_letter(self, penpal_name, letter_index):
        if not self.use_postgres:
            return self.delete_letter_file(penpal_name, letter_index)
        conn = self.get_connection()
        if not conn:
            return False
        try:
            cur = conn.cursor()
            cur.execute("SELECT id FROM penpals WHERE name = %s", (penpal_name,))
            result = cur.fetchone()
            if not result:
                return False
            penpal_id = result[0]
            cur.execute(
                "SELECT id FROM letters WHERE penpal_id = %s ORDER BY date_received",
                (penpal_id,)
            )
            letters = cur.fetchall()
            if 0 <= letter_index < len(letters):
                letter_id = letters[letter_index][0]
                cur.execute("DELETE FROM letters WHERE id = %s", (letter_id,))
                conn.commit()
                return True
            return False
        except Exception as e:
            print(f"Error deleting letter: {e}")
            conn.rollback()
            return False
        finally:
            cur.close()
            conn.close()
    
    def add_note(self, penpal_name, note):
        """Add a note about a penpal"""
        if not self.use_postgres:
            return self.add_note_file(penpal_name, note)
        
        conn = self.get_connection()
        if not conn:
            return False
        
        try:
            cur = conn.cursor()
            
            # Get penpal ID
            cur.execute("SELECT id FROM penpals WHERE name = %s", (penpal_name,))
            result = cur.fetchone()
            if not result:
                print(f"Penpal {penpal_name} not found")
                return False
            
            penpal_id = result[0]
            
            # Add note
            cur.execute(
                "INSERT INTO notes (penpal_id, note) VALUES (%s, %s)",
                (penpal_id, note)
            )
            conn.commit()
            print(f"Added note for {penpal_name}: {note[:50]}...")
            return True
            
        except Exception as e:
            print(f"Error adding note: {e}")
            conn.rollback()
            return False
        finally:
            cur.close()
            conn.close()
    
    def delete_note(self, penpal_name, note_index):
        """Delete a note about a penpal"""
        if not self.use_postgres:
            return self.delete_note_file(penpal_name, note_index)
        
        conn = self.get_connection()
        if not conn:
            return False
        
        try:
            cur = conn.cursor()
            
            # Get penpal ID and notes
            cur.execute("SELECT id FROM penpals WHERE name = %s", (penpal_name,))
            result = cur.fetchone()
            if not result:
                return False
            
            penpal_id = result[0]
            
            # Get notes ordered by date_added to match the index
            cur.execute(
                "SELECT id, note FROM notes WHERE penpal_id = %s ORDER BY date_added",
                (penpal_id,)
            )
            notes = cur.fetchall()
            
            if 0 <= note_index < len(notes):
                note_id, note_text = notes[note_index]
                cur.execute("DELETE FROM notes WHERE id = %s", (note_id,))
                conn.commit()
                print(f"Deleted note for {penpal_name}: {note_text[:50]}...")
                return True
            else:
                print(f"Note index {note_index} out of range for {penpal_name}")
                return False
                
        except Exception as e:
            print(f"Error deleting note: {e}")
            conn.rollback()
            return False
        finally:
            cur.close()
            conn.close()
    
    def get_penpal(self, name):
        """Get penpal data"""
        if not self.use_postgres:
            return self.get_penpal_file(name)
        
        conn = self.get_connection()
        if not conn:
            return None
        
        try:
            cur = conn.cursor()
            
            # Get penpal info
            cur.execute(
                "SELECT id, name, country, created_date FROM penpals WHERE name = %s",
                (name,)
            )
            penpal_data = cur.fetchone()
            if not penpal_data:
                return None
            
            penpal_id, penpal_name, country, created_date = penpal_data
            
            # Get letters
            cur.execute(
                "SELECT content, date_received, date_added FROM letters WHERE penpal_id = %s ORDER BY date_received DESC",
                (penpal_id,)
            )
            letters = []
            for content, date_received, date_added in cur.fetchall():
                letters.append({
                    "content": content,
                    "date_received": date_received.isoformat(),
                    "date_added": date_added.isoformat()
                })
            
            # Get notes
            cur.execute(
                "SELECT note, date_added FROM notes WHERE penpal_id = %s ORDER BY date_added",
                (penpal_id,)
            )
            notes = []
            for note, date_added in cur.fetchall():
                notes.append({
                    "note": note,
                    "date_added": date_added.isoformat()
                })
            
            return {
                "name": penpal_name,
                "country": country,
                "letters": letters,
                "notes": notes,
                "created_date": created_date.isoformat()
            }
            
        except Exception as e:
            print(f"Error getting penpal: {e}")
            return None
        finally:
            cur.close()
            conn.close()
    
    def get_all_penpals(self):
        """Get all penpals with summary info"""
        if not self.use_postgres:
            return self.get_all_penpals_file()
        
        conn = self.get_connection()
        if not conn:
            return []
        
        try:
            cur = conn.cursor()
            
            cur.execute('''
                SELECT 
                    p.name,
                    p.country,
                    COUNT(DISTINCT l.id) as letter_count,
                    COUNT(DISTINCT n.id) as note_count,
                    MAX(l.date_received) as last_letter
                FROM penpals p
                LEFT JOIN letters l ON p.id = l.penpal_id
                LEFT JOIN notes n ON p.id = n.penpal_id
                GROUP BY p.id, p.name, p.country
                ORDER BY last_letter DESC NULLS LAST
            ''')
            
            penpals = []
            for name, country, letter_count, note_count, last_letter in cur.fetchall():
                penpals.append({
                    "name": name,
                    "country": country,
                    "letter_count": letter_count,
                    "note_count": note_count,
                    "last_letter": last_letter.isoformat() if last_letter else None
                })
            
            return penpals
            
        except Exception as e:
            print(f"Error getting all penpals: {e}")
            return []
        finally:
            cur.close()
            conn.close()
    
    def search_letters(self, query):
        """Search letters by content"""
        if not self.use_postgres:
            return self.search_letters_file(query)
        
        conn = self.get_connection()
        if not conn:
            return []
        
        try:
            cur = conn.cursor()
            
            cur.execute('''
                SELECT 
                    p.name,
                    p.country,
                    l.content,
                    l.date_received,
                    l.date_added
                FROM letters l
                JOIN penpals p ON l.penpal_id = p.id
                WHERE LOWER(l.content) LIKE LOWER(%s)
                ORDER BY l.date_received DESC
            ''', (f'%{query}%',))
            
            results = []
            for name, country, content, date_received, date_added in cur.fetchall():
                results.append({
                    "penpal_name": name,
                    "country": country,
                    "letter": {
                        "content": content,
                        "date_received": date_received.isoformat(),
                        "date_added": date_added.isoformat()
                    },
                    "preview": self.get_preview(content, query, 200)
                })
            
            return results
            
        except Exception as e:
            print(f"Error searching letters: {e}")
            return []
        finally:
            cur.close()
            conn.close()
    
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
        if not self.use_postgres:
            return self.get_stats_file()
        
        conn = self.get_connection()
        if not conn:
            return {"total_penpals": 0, "total_letters": 0, "countries": 0, "country_list": []}
        
        try:
            cur = conn.cursor()
            
            # Get total penpals
            cur.execute("SELECT COUNT(*) FROM penpals")
            total_penpals = cur.fetchone()[0]
            
            # Get total letters
            cur.execute("SELECT COUNT(*) FROM letters")
            total_letters = cur.fetchone()[0]
            
            # Get countries
            cur.execute("SELECT DISTINCT country FROM penpals ORDER BY country")
            countries = [row[0] for row in cur.fetchall()]
            
            return {
                "total_penpals": total_penpals,
                "total_letters": total_letters,
                "countries": len(countries),
                "country_list": countries
            }
            
        except Exception as e:
            print(f"Error getting stats: {e}")
            return {"total_penpals": 0, "total_letters": 0, "countries": 0, "country_list": []}
        finally:
            cur.close()
            conn.close()
    
    # File-based fallback methods (simplified versions)
    def load_from_file(self):
        """Load data from file"""
        try:
            if os.path.exists('letters_data.json'):
                with open('letters_data.json', 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            print(f"Error loading from file: {e}")
        return {"penpals": {}}
    
    def save_to_file(self, data):
        """Save data to file"""
        try:
            with open('letters_data.json', 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"Error saving to file: {e}")
            return False
    
    # File fallback methods (implement basic functionality)
    def add_penpal_file(self, name, country):
        data = self.load_from_file()
        if name not in data["penpals"]:
            data["penpals"][name] = {
                "country": country,
                "letters": [],
                "notes": [],
                "created_date": datetime.now().isoformat()
            }
            return self.save_to_file(data)
        return False
    
    def add_letter_file(self, penpal_name, content, date_received=None):
        data = self.load_from_file()
        if penpal_name in data["penpals"]:
            if date_received is None:
                date_received = datetime.now().isoformat()
            
            letter = {
                "content": content,
                "date_received": date_received,
                "date_added": datetime.now().isoformat()
            }
            data["penpals"][penpal_name]["letters"].append(letter)
            return self.save_to_file(data)
        return False
    
    def add_note_file(self, penpal_name, note):
        data = self.load_from_file()
        if penpal_name in data["penpals"]:
            note_data = {
                "note": note,
                "date_added": datetime.now().isoformat()
            }
            data["penpals"][penpal_name]["notes"].append(note_data)
            return self.save_to_file(data)
        return False
    
    def delete_note_file(self, penpal_name, note_index):
        data = self.load_from_file()
        if (penpal_name in data["penpals"] and 
            0 <= note_index < len(data["penpals"][penpal_name]["notes"])):
            del data["penpals"][penpal_name]["notes"][note_index]
            return self.save_to_file(data)
        return False
    
    def get_penpal_file(self, name):
        data = self.load_from_file()
        return data["penpals"].get(name)
    
    def get_all_penpals_file(self):
        data = self.load_from_file()
        penpals = []
        for name, penpal_data in data["penpals"].items():
            penpal_info = {
                "name": name,
                "country": penpal_data["country"],
                "letter_count": len(penpal_data["letters"]),
                "note_count": len(penpal_data["notes"]),
                "last_letter": None
            }
            
            if penpal_data["letters"]:
                last_letter = max(penpal_data["letters"], key=lambda x: x.get("date_received", ""))
                penpal_info["last_letter"] = last_letter.get("date_received")
            
            penpals.append(penpal_info)
        
        penpals.sort(key=lambda x: x["last_letter"] or "0000-00-00", reverse=True)
        return penpals
    
    def search_letters_file(self, query):
        data = self.load_from_file()
        results = []
        query_lower = query.lower()
        
        for penpal_name, penpal_data in data["penpals"].items():
            for letter in penpal_data["letters"]:
                if query_lower in letter["content"].lower():
                    results.append({
                        "penpal_name": penpal_name,
                        "country": penpal_data["country"],
                        "letter": letter,
                        "preview": self.get_preview(letter["content"], query, 200)
                    })
        
        return results
    
    def get_stats_file(self):
        data = self.load_from_file()
        total_penpals = len(data["penpals"])
        total_letters = sum(len(penpal["letters"]) for penpal in data["penpals"].values())
        countries = set(penpal["country"] for penpal in data["penpals"].values())
        
        return {
            "total_penpals": total_penpals,
            "total_letters": total_letters,
            "countries": len(countries),
            "country_list": sorted(list(countries))
        }
