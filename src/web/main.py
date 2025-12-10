from flask import Flask, render_template, jsonify, request
import sqlite3
import sys
from pathlib import Path
import logging
import math

# Add project root to the Python path
sys.path.append(str(Path(__file__).resolve().parents[2]))

import config

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Define the web app and explicitly set the template folder
app = Flask(__name__, template_folder='templates')

# Path to the database from the unified config
DB_PATH = config.DB_PATH

def get_db_connection():
    """Creates a database connection. Returns None on error."""
    try:
        if not DB_PATH.exists():
            logger.error(f"Database file not found at {DB_PATH}")
            return None
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        return conn
    except sqlite3.Error as e:
        logger.error(f"Database connection error: {e}")
        return None

@app.route('/')
def index():
    """Page 1: Dashboard with statistics."""
    conn = get_db_connection()
    if not conn:
        return render_template('error.html', message="Could not connect to the database."), 500

    cursor = conn.cursor()
    
    try:
        cursor.execute('SELECT COUNT(*) FROM messages')
        total_messages = cursor.fetchone()[0]

        cursor.execute('SELECT COUNT(*) FROM messages WHERE summarized = 1')
        analyzed_messages = cursor.fetchone()[0]

        cursor.execute('SELECT MAX(created_at) FROM summaries')
        last_summary = cursor.fetchone()[0]
    except sqlite3.OperationalError as e:
        conn.close()
        # This can happen if tables don't exist yet
        return render_template('error.html', message=f"Database query failed. Have you run the bots to populate the data? Error: {e}"), 500

    conn.close()

    stats = {
        'total_messages': total_messages,
        'analyzed_messages': analyzed_messages,
        'last_summary': last_summary or 'N/A'
    }
    return render_template('index.html', stats=stats)


@app.route('/messages')
def list_messages():
    """Page 2: A paginated and tabbed list of all messages."""
    conn = get_db_connection()
    if not conn:
        return render_template('error.html', message="Could not connect to the database."), 500

    cursor = conn.cursor()
    
    # Pagination settings
    page = request.args.get('page', 1, type=int)
    per_page = 20
    offset = (page - 1) * per_page
    
    # Tab settings
    tab = request.args.get('tab', 'new', type=str)
    summarized_filter = 1 if tab == 'processed' else 0

    try:
        # Get total count for pagination
        cursor.execute('SELECT COUNT(*) FROM messages WHERE summarized = ?', (summarized_filter,))
        total = cursor.fetchone()[0]
        total_pages = math.ceil(total / per_page)
        
        # Get messages for the current page
        query = '''
            SELECT id, chat_id, sender, text, date, summarized 
            FROM messages 
            WHERE summarized = ?
            ORDER BY date DESC 
            LIMIT ? OFFSET ?
        '''
        cursor.execute(query, (summarized_filter, per_page, offset))
        messages = cursor.fetchall()

    except sqlite3.OperationalError as e:
        conn.close()
        return render_template('error.html', message=f"Database query failed: {e}"), 500

    conn.close()
    
    return render_template(
        'messages.html', 
        messages=messages,
        page=page,
        total_pages=total_pages,
        tab=tab
    )

@app.route('/summaries')
def list_summaries():
    """Page 3: A list of all summaries."""
    conn = get_db_connection()
    if not conn:
        return render_template('error.html', message="Could not connect to the database."), 500

    cursor = conn.cursor()
    try:
        cursor.execute('SELECT id, summary_text, message_ids, message_count, created_at FROM summaries ORDER BY created_at DESC')
        summaries = cursor.fetchall()
    except sqlite3.OperationalError as e:
        conn.close()
        return render_template('error.html', message=f"Database query failed. Have you run the bot to generate summaries? Error: {e}"), 500
        
    conn.close()
    return render_template('summaries.html', summaries=summaries)

@app.route('/api/messages_by_ids')
def get_messages_by_ids():
    """API endpoint to get details for multiple messages by their IDs."""
    message_ids_str = request.args.get('ids')
    if not message_ids_str:
        return jsonify({"error": "No message IDs provided"}), 400

    message_ids = [int(id) for id in message_ids_str.split(',') if id.isdigit()]
    if not message_ids:
        return jsonify({"error": "Invalid message IDs"}), 400

    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Database connection failed"}), 500

    cursor = conn.cursor()
    
    placeholders = ','.join('?' for _ in message_ids)
    query = f'SELECT id, sender, chat_id, date, text FROM messages WHERE id IN ({placeholders})'
    
    cursor.execute(query, message_ids)
    messages = [dict(row) for row in cursor.fetchall()]
    conn.close()
    
    return jsonify(messages)

def run():
    """Запускает веб-приложение Flask."""
    if not DB_PATH.exists():
        print("="*60)
        print("WARNING: Database file not found!")
        print(f"Expected location: {DB_PATH}")
        print("Please ensure the scraper has been run at least once (`python run.py scrape`).")
        print("="*60)
    
    logger.info("Запуск веб-приложения Flask...")
    app.run(debug=True, port=5001)

if __name__ == '__main__':
    run()
