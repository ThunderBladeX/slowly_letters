from flask import Flask, render_template, request, redirect, url_for, jsonify
import json
import os
from datetime import datetime
from letters import LetterManager
import google.generativeai as genai

app = Flask(__name__)
letter_manager = LetterManager()

# Configure Gemini AI
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel('gemini-pro')
else:
    model = None

@app.route('/')
def index():
    penpals = letter_manager.get_all_penpals()
    return render_template('index.html', penpals=penpals, letter_manager=letter_manager)

@app.route('/penpal/<path:penpal_name>')
def penpal_details(penpal_name):
    penpal = letter_manager.get_penpal(penpal_name)
    if not penpal:
        return redirect(url_for('index'))
    return render_template('penpal.html', penpal=penpal, gemini_available=bool(model))

@app.route('/add_penpal', methods=['GET', 'POST'])
def add_penpal():
    if request.method == 'POST':
        name = request.form['name']
        country = request.form['country']
        letter_manager.add_penpal(name, country)
        return redirect(url_for('index'))
    return render_template('add_penpal.html')

@app.route('/add_letter', methods=['POST'])
def add_letter():
    print("=== /add_letter called ===")
    penpal_name = request.form['penpal_name']
    content = request.form['content']
    date_received = request.form['date_received']
    auto_extract = request.form.get('auto_extract') == 'on'

    print(f"Submitted penpal_name: '{penpal_name}'")
    print(f"Existing penpals: {[p['name'] for p in letter_manager.get_all_penpals()]}")
    
    success = letter_manager.add_letter(penpal_name, content, date_received)
    if not success:
        # flash a message, or render a template with an error
        return "Penpal not found or error adding letter.", 400
    
    # Add the letter first
    letter_manager.add_letter(penpal_name, content, date_received)
    
    # If auto-extract is enabled and Gemini is configured, extract information
    if auto_extract and model:
        try:
            extracted_info = extract_info_from_letter(content, penpal_name)
            if extracted_info:
                for info in extracted_info:
                    letter_manager.add_note(penpal_name, info)
        except Exception as e:
            print(f"Error extracting info with Gemini: {e}")
    
    return redirect(url_for('penpal_details', penpal_name=penpal_name))

def extract_info_from_letter(letter_content, penpal_name):
    """Extract key information from letter using Gemini AI"""
    if not model:
        return []
    
    # Get existing notes to avoid duplicates
    existing_notes = letter_manager.get_penpal(penpal_name).get('notes', [])
    existing_notes_text = ' '.join([note['note'] for note in existing_notes])
    
    prompt = f"""
    Analyze this letter from my pen pal {penpal_name} and extract key personal information that I should remember about them. 

    Focus on:
    - Personal preferences (favorite colors, foods, hobbies, etc.)
    - Interests and activities they enjoy
    - Their profession, studies, or work
    - Family members or pets mentioned
    - Places they've been or want to visit
    - Important life events or milestones
    - Personality traits or characteristics
    - Cultural details about their country/city

    Letter content:
    {letter_content}

    Existing notes I already have about {penpal_name}:
    {existing_notes_text}

    Please provide 3-5 short, concise bullet points of NEW information (avoid duplicating existing notes). 
    Each point should be a single sentence, like "Loves Italian food" or "Studies architecture at university" or "Has a cat named Luna".
    
    If there's no significant new personal information to extract, respond with "No new information to extract."

    Format your response as a simple list, one item per line. CRITICALLY IMPORTANT: DO NOT use any bullet points, hyphens, numbers, or any other prefixes before each item.
    """
    
    try:
        response = model.generate_content(prompt)
        result = response.text.strip()
        
        if "No new information to extract" in result:
            return []
        
        # Split into individual notes and clean them up
        notes = [note.strip() for note in result.split('\n') if note.strip()]
        # Remove any bullet points or numbers that might have been added
        cleaned_notes = []
        for note in notes:
            # Remove common bullet point prefixes
            note = note.lstrip('•-*123456789. ')
            if note and len(note) > 5:  # Only keep substantial notes
                cleaned_notes.append(note)
        
        return cleaned_notes[:5]  # Limit to 5 notes max
        
    except Exception as e:
        print(f"Gemini API error: {e}")
        return []

@app.route('/delete_letter', methods=['POST'])
def delete_letter():
    penpal_name = request.form['penpal_name']
    letter_index = int(request.form['letter_index'])
    letter_manager.delete_letter(penpal_name, letter_index)
    return redirect(url_for('penpal_details', penpal_name=penpal_name))

@app.route('/add_note', methods=['POST'])
def add_note():
    penpal_name = request.form['penpal_name']
    note = request.form['note']
    letter_manager.add_note(penpal_name, note)
    return redirect(url_for('penpal_details', penpal_name=penpal_name))

@app.route('/delete_note', methods=['POST'])
def delete_note():
    penpal_name = request.form['penpal_name']
    note_index = int(request.form['note_index'])
    letter_manager.delete_note(penpal_name, note_index)
    return redirect(url_for('penpal_details', penpal_name=penpal_name))

@app.route('/search')
def search():
    query = request.args.get('q', '')
    results = letter_manager.search_letters(query)
    return render_template('search_results.html', results=results, query=query)

@app.route('/extract_from_letter', methods=['POST'])
def extract_from_letter():
    """Manually extract information from a specific letter"""
    penpal_name = request.form['penpal_name']
    letter_content = request.form['letter_content']
    
    if model:
        try:
            extracted_info = extract_info_from_letter(letter_content, penpal_name)
            if extracted_info:
                for info in extracted_info:
                    letter_manager.add_note(penpal_name, f"[AI] {info}")
        except Exception as e:
            print(f"Error extracting info: {e}")
    
    return redirect(url_for('penpal_details', penpal_name=penpal_name))

if __name__ == '__main__':
    app.run(debug=True)
