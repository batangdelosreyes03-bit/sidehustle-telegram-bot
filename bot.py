# ===========================
# SIDEHUSTLE BOT v4.0 - RAILWAY READY
# WITH FULL ADMIN MONITORING
# ===========================

import telebot
from telebot import types
import sqlite3
import time
import threading
from datetime import datetime, timedelta
import schedule
import os

# ========= LOAD ENVIRONMENT VARIABLES =========
# For Railway/Local development
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
ADMIN_ID = os.getenv("ADMIN_ID", "")

# Convert ADMIN_ID to integer if exists
if ADMIN_ID and ADMIN_ID.isdigit():
    ADMIN_ID = int(ADMIN_ID)
else:
    ADMIN_ID = None

# ========= VALIDATE CONFIG =========
if not BOT_TOKEN:
    print("❌ ERROR: BOT_TOKEN not set in environment variables!")
    print("💡 Add BOT_TOKEN in Railway Variables or .env file")
    exit(1)

if not ADMIN_ID:
    print("⚠️ WARNING: ADMIN_ID not set. Some admin features will be disabled.")
    print("💡 Run /getid command to get your Telegram ID")

bot = telebot.TeleBot(BOT_TOKEN)

# ========= ENHANCED DATABASE =========
def get_db_connection():
    """Get new database connection for each thread"""
    # Use /tmp for Railway compatibility
    db_path = os.getenv("DATABASE_URL", "/tmp/sidehustle.db")
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_database():
    """Initialize database tables"""
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Users table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        role TEXT,
        skills TEXT DEFAULT '',
        location TEXT DEFAULT '',
        is_banned INTEGER DEFAULT 0,
        created TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    
    # Jobs table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS jobs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        client_id INTEGER,
        title TEXT,
        description TEXT,
        budget TEXT,
        status TEXT DEFAULT 'open',
        created TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    
    # ========= MONITORING TABLES =========
    
    # User activity log
    cur.execute("""
    CREATE TABLE IF NOT EXISTS user_activity (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        action TEXT,
        details TEXT,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    
    # Job views tracker
    cur.execute("""
    CREATE TABLE IF NOT EXISTS job_views (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        job_id INTEGER,
        viewer_id INTEGER,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    
    # Platform metrics
    cur.execute("""
    CREATE TABLE IF NOT EXISTS daily_metrics (
        date DATE PRIMARY KEY,
        new_users INTEGER DEFAULT 0,
        new_jobs INTEGER DEFAULT 0,
        active_users INTEGER DEFAULT 0
    )
    """)
    
    conn.commit()
    conn.close()
    print("✅ Database initialized with monitoring tables")

# Initialize database
init_database()

# Store user state (in memory)
user_state = {}

# ========= MONITORING FUNCTIONS =========
def log_activity(user_id, action, details=""):
    """Log user activity"""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute("""
            INSERT INTO user_activity (user_id, action, details)
            VALUES (?, ?, ?)
        """, (user_id, action, details))
        
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Error logging activity: {e}")

def update_daily_metrics():
    """Update daily platform metrics"""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        today = datetime.now().strftime('%Y-%m-%d')
        
        # Count new users today
        cur.execute("""
            SELECT COUNT(*) FROM users 
            WHERE DATE(created) = ?
        """, (today,))
        new_users = cur.fetchone()[0]
        
        # Count new jobs today
        cur.execute("""
            SELECT COUNT(*) FROM jobs 
            WHERE DATE(created) = ?
        """, (today,))
        new_jobs = cur.fetchone()[0]
        
        # Count active users today
        cur.execute("""
            SELECT COUNT(DISTINCT user_id) FROM user_activity 
            WHERE DATE(timestamp) = ?
        """, (today,))
        active_users = cur.fetchone()[0]
        
        # Update or insert
        cur.execute("""
            INSERT OR REPLACE INTO daily_metrics 
            (date, new_users, new_jobs, active_users)
            VALUES (?, ?, ?, ?)
        """, (today, new_users, new_jobs, active_users))
        
        conn.commit()
        conn.close()
        print(f"📊 Updated daily metrics for {today}")
    except Exception as e:
        print(f"Error updating metrics: {e}")

# Schedule daily metrics update
def schedule_metrics_update():
    schedule.every().day.at("23:59").do(update_daily_metrics)
    
    while True:
        schedule.run_pending()
        time.sleep(60)

# Start metrics thread
metrics_thread = threading.Thread(target=schedule_metrics_update, daemon=True)
metrics_thread.start()

# ========= HELPER FUNCTIONS =========
def save_user(user_id, username, role):
    conn = get_db_connection()
    cur = conn.cursor()
    
    cur.execute("""
        INSERT OR REPLACE INTO users (user_id, username, role)
        VALUES (?, ?, ?)
    """, (user_id, username, role))
    
    conn.commit()
    conn.close()

def create_job(client_id, title, description, budget):
    conn = get_db_connection()
    cur = conn.cursor()
    
    cur.execute("""
        INSERT INTO jobs (client_id, title, description, budget)
        VALUES (?, ?, ?, ?)
    """, (client_id, title, description, budget))
    
    job_id = cur.lastrowid
    conn.commit()
    conn.close()
    
    return job_id

def get_jobs():
    conn = get_db_connection()
    cur = conn.cursor()
    
    cur.execute("""
        SELECT id, title, budget, created 
        FROM jobs 
        WHERE status='open' 
        ORDER BY id DESC 
        LIMIT 10
    """)
    
    jobs = cur.fetchall()
    conn.close()
    
    return jobs

def get_freelancers():
    conn = get_db_connection()
    cur = conn.cursor()
    
    cur.execute("SELECT user_id FROM users WHERE role='freelancer' AND is_banned=0")
    freelancers = cur.fetchall()
    
    conn.close()
    return freelancers

def is_admin(user_id):
    """Check if user is admin"""
    if not ADMIN_ID:
        return False
    return user_id == ADMIN_ID

# ========= START COMMAND =========
@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id
    username = message.from_user.username or ""
    
    # Log activity
    log_activity(user_id, "start_command", "User started bot")
    
    # Check if admin
    if is_admin(user_id):
        bot.send_message(message.chat.id, 
                        "👑 *ADMIN MODE ACTIVATED*\n\n"
                        "You have access to admin commands:\n"
                        "/dashboard - View real-time stats\n"
                        "/users - View all users\n"
                        "/alljobs - View all jobs\n"
                        "/dailyreport - Daily report\n"
                        "/analytics - Detailed analytics\n"
                        "/viewuser - View user details\n"
                        "/broadcast - Send message to all\n"
                        "/getid - Get your Telegram ID\n\n"
                        "To use as normal user, continue below.",
                        parse_mode="Markdown")
    
    text = """
👋 *Welcome to SideHustle Bot!*

Choose your role:
• 👤 **Freelancer** - Find work opportunities
• 🧑‍💼 **Client** - Post jobs and hire talent

⚠️ *Important:*
- All payments are direct
- Verify before transacting
- This platform is free
"""
    
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("👤 I'm a Freelancer", "🧑‍💼 I'm a Client")
    
    bot.send_message(message.chat.id, text, parse_mode="Markdown", reply_markup=markup)

# ========= ROLE SELECTION =========
@bot.message_handler(func=lambda m: m.text in ["👤 I'm a Freelancer", "🧑‍💼 I'm a Client"])
def choose_role(message):
    user_id = message.from_user.id
    username = message.from_user.username or ""
    
    if "Freelancer" in message.text:
        role = "freelancer"
    else:
        role = "client"
    
    # Log activity
    log_activity(user_id, "role_selected", f"Selected role: {role}")
    
    # Save user
    save_user(user_id, username, role)
    
    if role == "freelancer":
        user_state[user_id] = {"step": "ask_skills"}
        bot.send_message(message.chat.id, 
                        "🛠️ *What are your skills?*\nExample: Web Design, Writing, Programming",
                        parse_mode="Markdown",
                        reply_markup=types.ReplyKeyboardRemove())
    else:
        user_state[user_id] = {"step": "job_title"}
        bot.send_message(message.chat.id,
                        "📝 *Post a Job*\n\nEnter job title:",
                        parse_mode="Markdown",
                        reply_markup=types.ReplyKeyboardRemove())

# ========= FREELANCER FLOW =========
@bot.message_handler(func=lambda m: 
                     user_state.get(m.from_user.id, {}).get("step") == "ask_skills")
def handle_skills(message):
    user_id = message.from_user.id
    skills = message.text
    
    # Log activity
    log_activity(user_id, "set_skills", f"Skills: {skills[:50]}")
    
    # Save skills to database
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("UPDATE users SET skills=? WHERE user_id=?", (skills, user_id))
    conn.commit()
    conn.close()
    
    user_state[user_id] = {"step": "ask_location"}
    bot.send_message(message.chat.id, 
                    "📍 *Where are you located?*\nExample: Manila, Remote, Philippines",
                    parse_mode="Markdown")

@bot.message_handler(func=lambda m: 
                     user_state.get(m.from_user.id, {}).get("step") == "ask_location")
def handle_location(message):
    user_id = message.from_user.id
    location = message.text
    
    # Log activity
    log_activity(user_id, "set_location", f"Location: {location}")
    
    # Save location to database
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("UPDATE users SET location=? WHERE user_id=?", (location, user_id))
    conn.commit()
    conn.close()
    
    # Clear state
    user_state.pop(user_id, None)
    
    # Show success message
    bot.send_message(message.chat.id,
                    "✅ *Profile Complete!*\n\n"
                    "You can now browse available jobs.\n"
                    "Use: /jobs - See available work\n"
                    "/profile - View your profile",
                    parse_mode="Markdown")

# ========= CLIENT FLOW =========
@bot.message_handler(func=lambda m: 
                     user_state.get(m.from_user.id, {}).get("step") == "job_title")
def handle_job_title(message):
    user_id = message.from_user.id
    user_state[user_id] = {
        "step": "job_description",
        "title": message.text
    }
    
    bot.send_message(message.chat.id, 
                    "📄 *Job Description:*\n\nDescribe what needs to be done.",
                    parse_mode="Markdown")

@bot.message_handler(func=lambda m: 
                     user_state.get(m.from_user.id, {}).get("step") == "job_description")
def handle_job_description(message):
    user_id = message.from_user.id
    user_state[user_id]["description"] = message.text
    user_state[user_id]["step"] = "job_budget"
    
    bot.send_message(message.chat.id,
                    "💰 *Budget:*\nExample: $100, ₱5000, Negotiable",
                    parse_mode="Markdown")

@bot.message_handler(func=lambda m: 
                     user_state.get(m.from_user.id, {}).get("step") == "job_budget")
def handle_job_budget(message):
    user_id = message.from_user.id
    job_data = user_state[user_id]
    
    # Log activity
    log_activity(user_id, "post_job", f"Job: {job_data['title'][:30]}...")
    
    # Create job in database
    job_id = create_job(user_id, job_data["title"], job_data["description"], message.text)
    
    # Clear state
    user_state.pop(user_id, None)
    
    # Send confirmation
    bot.send_message(message.chat.id,
                    f"✅ *Job Posted Successfully!*\n\n"
                    f"*Title:* {job_data['title']}\n"
                    f"*Budget:* {message.text}\n"
                    f"*Job ID:* #{job_id}\n\n"
                    f"Freelancers will be notified.\n\n"
                    f"⚠️ *Remember:*\n"
                    f"• Payments are direct between parties\n"
                    f"• Verify freelancer identity\n"
                    f"• Use milestones for large projects",
                    parse_mode="Markdown")
    
    # Notify freelancers
    try:
        freelancers = get_freelancers()
        
        for (fid,) in freelancers:
            try:
                bot.send_message(fid,
                                f"📢 *NEW JOB AVAILABLE!*\n\n"
                                f"Title: {job_data['title']}\n"
                                f"Budget: {message.text}\n\n"
                                f"Use /jobs to browse all available work.")
                
                # Log notification
                log_activity(fid, "job_notification", f"Notified about job #{job_id}")
            except:
                pass  # Skip if can't send to user
    except:
        pass  # Skip if error in notification

# ========= JOB BROWSING =========
@bot.message_handler(commands=['jobs'])
def list_jobs_command(message):
    user_id = message.from_user.id
    
    # Log activity
    log_activity(user_id, "view_jobs", "Browsed job listings")
    
    jobs = get_jobs()
    
    if not jobs:
        bot.send_message(message.chat.id, 
                        "📭 *No jobs available yet.*\n\n"
                        "Check back later or post your own job!",
                        parse_mode="Markdown")
        return
    
    text = "📋 *Available Jobs*\n\n"
    
    for job in jobs:
        job_id = job[0]
        title = job[1]
        budget = job[2]
        created = job[3]
        
        text += f"*#{job_id}* - {title}\n"
        text += f"💰 *Budget:* {budget}\n"
        text += f"📅 *Posted:* {created[:10]}\n\n"
    
    text += "💡 *How to apply:*\nContact the client directly."
    
    bot.send_message(message.chat.id, text, parse_mode="Markdown")

# ========= PROFILE COMMAND =========
@bot.message_handler(commands=['profile'])
def profile_command(message):
    user_id = message.from_user.id
    
    # Log activity
    log_activity(user_id, "view_profile", "Viewed own profile")
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    cur.execute("SELECT username, role, skills, location FROM users WHERE user_id=?", (user_id,))
    user = cur.fetchone()
    
    conn.close()
    
    if not user:
        bot.send_message(message.chat.id, 
                        "❌ *Profile not found.*\n\n"
                        "Please use /start to create your profile.",
                        parse_mode="Markdown")
        return
    
    username, role, skills, location = user
    
    text = f"""
👤 *YOUR PROFILE*

*Basic Information:*
• Username: @{username or 'N/A'}
• Role: {role.title() if role else 'Not set'}
• Skills: {skills or 'Not set'}
• Location: {location or 'Not set'}

*Quick Stats:*
• Jobs Posted: 0
• Jobs Applied: 0
• Member Since: Today

*Commands:*
/jobs - Browse available work
/help - Get assistance
"""
    
    bot.send_message(message.chat.id, text, parse_mode="Markdown")

# ========= HELP COMMAND =========
@bot.message_handler(commands=['help'])
def help_command(message):
    user_id = message.from_user.id
    
    # Log activity
    log_activity(user_id, "view_help", "Viewed help")
    
    text = """
🆘 *HELP & COMMANDS*

*For Everyone:*
/start - Start the bot
/profile - View your profile
/jobs - Browse available jobs
/help - Show this message
/getid - Get your Telegram ID

*For Freelancers:*
1. Register as freelancer
2. Set your skills & location
3. Browse /jobs
4. Contact clients directly

*For Clients:*
1. Register as client
2. Post jobs via conversation
3. Review freelancers
4. Pay directly

⚠️ *SAFETY TIPS:*
• Verify identity before payment
• Use Telegram for communication
• Start with small projects
• Report issues immediately

📞 *Need Help?*
Contact admin via /start
"""
    
    bot.send_message(message.chat.id, text, parse_mode="Markdown")

# ========= GET ID COMMAND =========
@bot.message_handler(commands=['getid'])
def get_id_command(message):
    user_id = message.from_user.id
    username = message.from_user.username or "No username"
    
    text = f"""
📋 *YOUR TELEGRAM INFO*

*User ID:* `{user_id}`
*Username:* @{username}
*Name:* {message.from_user.first_name} {message.from_user.last_name or ''}

💡 *Your User ID is important for:*
• Admin verification
• Account recovery
• Technical support

⚠️ *Keep this information private!*
"""
    
    bot.send_message(message.chat.id, text, parse_mode="Markdown")
    
    # If this is admin, remind about ADMIN_ID
    if str(user_id) == str(ADMIN_ID):
        bot.send_message(message.chat.id,
                        f"👑 *ADMIN NOTE:*\nYour ID is `{user_id}`\n"
                        f"Add this to Railway Variables as ADMIN_ID",
                        parse_mode="Markdown")

# ========= ADMIN DASHBOARD =========
@bot.message_handler(commands=['dashboard'])
def admin_dashboard(message):
    if not is_admin(message.from_user.id):
        bot.send_message(message.chat.id, "🚫 Admin access required!")
        return
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Real-time stats
    cur.execute("SELECT COUNT(*) FROM users WHERE is_banned=0")
    total_users = cur.fetchone()[0]
    
    cur.execute("SELECT COUNT(*) FROM jobs")
    total_jobs = cur.fetchone()[0]
    
    # Today's stats
    today = datetime.now().strftime('%Y-%m-%d')
    
    cur.execute("SELECT COUNT(*) FROM users WHERE DATE(created) = ? AND is_banned=0", (today,))
    new_users_today = cur.fetchone()[0]
    
    cur.execute("SELECT COUNT(*) FROM jobs WHERE DATE(created) = ?", (today,))
    new_jobs_today = cur.fetchone()[0]
    
    # Active now (last 5 minutes)
    five_min_ago = (datetime.now() - timedelta(minutes=5)).strftime('%Y-%m-%d %H:%M:%S')
    cur.execute("SELECT COUNT(DISTINCT user_id) FROM user_activity WHERE timestamp > ?", 
                (five_min_ago,))
    active_now = cur.fetchone()[0]
    
    # Recent activities
    cur.execute("""
        SELECT ua.action, u.username, ua.timestamp
        FROM user_activity ua
        LEFT JOIN users u ON ua.user_id = u.user_id
        WHERE u.is_banned=0
        ORDER BY ua.timestamp DESC
        LIMIT 10
    """)
    recent_activities = cur.fetchall()
    
    conn.close()
    
    # Build dashboard
    text = f"""
📊 *REAL-TIME ADMIN DASHBOARD*
🕐 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
📍 *Host:* Railway

👥 *USER STATISTICS:*
• Total Users: {total_users}
• New Today: {new_users_today}
• Active Now: {active_now}

📋 *JOB STATISTICS:*
• Total Jobs: {total_jobs}
• New Today: {new_jobs_today}

📈 *RECENT ACTIVITIES:*
"""
    
    if recent_activities:
        for activity in recent_activities:
            action, username, timestamp = activity
            time_str = timestamp[11:16] if isinstance(timestamp, str) else timestamp[11:16]
            text += f"  • @{username or 'N/A'}: {action} at {time_str}\n"
    else:
        text += "  No recent activities\n"
    
    text += "\n⚡ *Quick Commands:*\n"
    text += "/users - View all users\n"
    text += "/alljobs - View all jobs\n"
    text += "/dailyreport - Daily report\n"
    text += "/analytics - Detailed analytics\n"
    text += "/viewuser [id] - View user details\n"
    text += "/broadcast [message] - Send to all users"
    
    bot.send_message(message.chat.id, text, parse_mode="Markdown")

# ========= ADMIN VIEW USERS =========
@bot.message_handler(commands=['users'])
def admin_users(message):
    if not is_admin(message.from_user.id):
        return
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Get all users
    cur.execute("""
        SELECT user_id, username, role, skills, location, created 
        FROM users 
        WHERE is_banned=0
        ORDER BY created DESC 
        LIMIT 20
    """)
    users = cur.fetchall()
    conn.close()
    
    if not users:
        bot.send_message(message.chat.id, "📭 No users registered yet.")
        return
    
    text = "👥 *REGISTERED USERS*\n\n"
    
    for user in users:
        user_id, username, role, skills, location, created = user
        
        text += f"👤 *User ID:* `{user_id}`\n"
        text += f"📛 *Username:* @{username or 'N/A'}\n"
        text += f"🎯 *Role:* {role.title() if role else 'N/A'}\n"
        text += f"🛠️ *Skills:* {skills[:30] if skills else 'N/A'}...\n"
        text += f"📍 *Location:* {location or 'N/A'}\n"
        text += f"📅 *Joined:* {created[:10]}\n"
        text += "─" * 30 + "\n\n"
    
    text += f"📊 **Total:** {len(users)} active users"
    
    bot.send_message(message.chat.id, text, parse_mode="Markdown")

# ========= ADMIN VIEW ALL JOBS =========
@bot.message_handler(commands=['alljobs'])
def admin_all_jobs(message):
    if not is_admin(message.from_user.id):
        return
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    cur.execute("""
        SELECT j.id, j.title, j.budget, j.status, u.username, j.created 
        FROM jobs j
        LEFT JOIN users u ON j.client_id = u.user_id
        ORDER BY j.id DESC 
        LIMIT 15
    """)
    jobs = cur.fetchall()
    conn.close()
    
    if not jobs:
        bot.send_message(message.chat.id, "📭 No jobs posted yet.")
        return
    
    text = "📋 *ALL JOBS*\n\n"
    
    for job in jobs:
        job_id, title, budget, status, username, created = job
        
        status_icon = "🟢" if status == 'open' else "🔴"
        
        text += f"{status_icon} *Job #{job_id}*\n"
        text += f"📌 *Title:* {title}\n"
        text += f"💰 *Budget:* {budget}\n"
        text += f"👤 *Client:* @{username or 'N/A'}\n"
        text += f"📊 *Status:* {status}\n"
        text += f"📅 *Posted:* {created[:10]}\n"
        text += "─" * 30 + "\n\n"
    
    bot.send_message(message.chat.id, text, parse_mode="Markdown")

# ========= ADMIN VIEW USER DETAILS =========
@bot.message_handler(commands=['viewuser'])
def view_user_detail(message):
    if not is_admin(message.from_user.id):
        return
    
    try:
        # Extract user ID from command
        parts = message.text.split()
        if len(parts) < 2:
            bot.send_message(message.chat.id, "❌ Usage: /viewuser user_id\nExample: /viewuser 123456789")
            return
        
        user_id = int(parts[1])
    except ValueError:
        bot.send_message(message.chat.id, "❌ Invalid user ID. Please provide a numeric ID.")
        return
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Get user info
    cur.execute("""
        SELECT username, role, skills, location, created, is_banned
        FROM users 
        WHERE user_id = ?
    """, (user_id,))
    
    user = cur.fetchone()
    
    if not user:
        bot.send_message(message.chat.id, f"❌ User ID `{user_id}` not found.")
        conn.close()
        return
    
    username, role, skills, location, created, is_banned = user
    
    # Get user's posted jobs
    cur.execute("SELECT COUNT(*) FROM jobs WHERE client_id = ?", (user_id,))
    jobs_posted = cur.fetchone()[0]
    
    # Get user activity
    cur.execute("""
        SELECT action, details, timestamp
        FROM user_activity
        WHERE user_id = ?
        ORDER BY timestamp DESC
        LIMIT 10
    """, (user_id,))
    
    activities = cur.fetchall()
    
    conn.close()
    
    # Build user detail message
    text = f"""
👤 *USER DETAILS: #{user_id}*

📝 *Basic Info:*
• Username: @{username or 'N/A'}
• Role: {role.title() if role else 'N/A'}
• Skills: {skills or 'N/A'}
• Location: {location or 'N/A'}
• Status: {"🔴 BANNED" if is_banned else "🟢 ACTIVE"}
• Joined: {created[:10] if created else 'N/A'}

📊 *Statistics:*
• Jobs Posted: {jobs_posted}

📈 *Recent Activities:*"""
    
    if activities:
        for activity in activities:
            action, details, timestamp = activity
            time_str = timestamp[11:16] if isinstance(timestamp, str) else timestamp[11:16]
            text += f"\n  • {action}: {details[:30]} at {time_str}"
    else:
        text += "\n  No recent activities"
    
    text += f"\n\n⚡ *Admin Actions:*\n"
    text += f"/ban_{user_id} - Ban this user\n"
    text += f"/unban_{user_id} - Unban this user"
    
    bot.send_message(message.chat.id, text, parse_mode="Markdown")

# ========= ADMIN BAN/UNBAN HANDLER =========
@bot.message_handler(func=lambda m: m.text.startswith('/ban_') or m.text.startswith('/unban_'))
def handle_ban_unban(message):
    if not is_admin(message.from_user.id):
        return
    
    try:
        # Extract command and user ID
        command = message.text.split('_')[0]
        user_id = int(message.text.split('_')[1])
        
        conn = get_db_connection()
        cur = conn.cursor()
        
        if command == '/ban':
            # Ban user
            cur.execute("UPDATE users SET is_banned=1 WHERE user_id=?", (user_id,))
            action = "banned"
            log_activity(user_id, "user_banned", f"Banned by admin {message.from_user.id}")
        else:
            # Unban user
            cur.execute("UPDATE users SET is_banned=0 WHERE user_id=?", (user_id,))
            action = "unbanned"
            log_activity(user_id, "user_unbanned", f"Unbanned by admin {message.from_user.id}")
        
        conn.commit()
        
        # Get username for confirmation
        cur.execute("SELECT username FROM users WHERE user_id=?", (user_id,))
        username = cur.fetchone()
        username = username[0] if username else "Unknown"
        
        conn.close()
        
        bot.send_message(message.chat.id,
                        f"✅ User @{username} (ID: {user_id}) has been {action}.",
                        parse_mode="Markdown")
        
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Error: {str(e)}")

# ========= ADMIN DAILY REPORT =========
@bot.message_handler(commands=['dailyreport'])
def daily_report(message):
    if not is_admin(message.from_user.id):
        return
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Get yesterday's date
    yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
    
    # Get daily metrics
    cur.execute("SELECT * FROM daily_metrics WHERE date = ?", (yesterday,))
    metrics = cur.fetchone()
    
    conn.close()
    
    if not metrics:
        bot.send_message(message.chat.id, f"📭 No data for {yesterday}")
        return
    
    date, new_users, new_jobs, active_users = metrics
    
    text = f"""
📅 *DAILY REPORT: {date}*

📊 *Platform Performance:*
• New Users: {new_users}
• New Jobs: {new_jobs}
• Active Users: {active_users}

📈 *Growth Analysis:*
• User Growth: {new_users} new/day
• Job Creation: {new_jobs} new/day

🎯 *Recommendations:*
{'✅ Excellent activity!' if active_users >= 10 else '⚠️ Need to increase engagement!'}
{'✅ Healthy job creation!' if new_jobs >= 3 else '⚠️ Encourage clients to post more!'}
"""
    
    bot.send_message(message.chat.id, text, parse_mode="Markdown")

# ========= ADMIN ANALYTICS =========
@bot.message_handler(commands=['analytics'])
def analytics(message):
    if not is_admin(message.from_user.id):
        return
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Get 7-day trend
    seven_days_ago = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
    
    cur.execute("""
        SELECT date, new_users, new_jobs, active_users
        FROM daily_metrics
        WHERE date >= ?
        ORDER BY date
    """, (seven_days_ago,))
    
    trends = cur.fetchall()
    conn.close()
    
    if not trends:
        bot.send_message(message.chat.id, "📭 No analytics data available yet.")
        return
    
    text = "📊 *7-DAY ANALYTICS*\n\n"
    
    for day in trends:
        date, users, jobs, active = day
        text += f"📅 {date[-5:]}: 👥{users} 💼{jobs} 🔥{active}\n"
    
    # Calculate averages
    total_users = sum(day[1] for day in trends)
    total_jobs = sum(day[2] for day in trends)
    total_active = sum(day[3] for day in trends)
    
    avg_users = total_users / len(trends) if trends else 0
    avg_jobs = total_jobs / len(trends) if trends else 0
    avg_active = total_active / len(trends) if trends else 0
    
    text += f"\n📈 *Weekly Totals:*\n"
    text += f"• Total New Users: {total_users}\n"
    text += f"• Total New Jobs: {total_jobs}\n"
    text += f"• Total Active Users: {total_active}\n\n"
    
    text += f"📊 *Daily Averages:*\n"
    text += f"• Avg Users/Day: {avg_users:.1f}\n"
    text += f"• Avg Jobs/Day: {avg_jobs:.1f}\n"
    text += f"• Avg Active/Day: {avg_active:.1f}\n\n"
    
    text += "📋 *Legend:*\n"
    text += "• 👥 = New Users\n"
    text += "• 💼 = New Jobs\n"
    text += "• 🔥 = Active Users\n"
    
    bot.send_message(message.chat.id, text, parse_mode="Markdown")

# ========= ADMIN BROADCAST =========
@bot.message_handler(commands=['broadcast'])
def broadcast_message(message):
    if not is_admin(message.from_user.id):
        return
    
    # Check if message has content
    if len(message.text.split()) < 2:
        bot.send_message(message.chat.id,
                        "❌ Usage: /broadcast your message here\n"
                        "Example: /broadcast New feature added! Check /help")
        return
    
    # Extract broadcast message
    broadcast_text = message.text.split(' ', 1)[1]
    
    # Confirmation
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("✅ Yes, Send to All", callback_data=f"confirm_broadcast:{broadcast_text}"),
        types.InlineKeyboardButton("❌ Cancel", callback_data="cancel_broadcast")
    )
    
    bot.send_message(message.chat.id,
                    f"📢 *BROADCAST CONFIRMATION*\n\n"
                    f"*Message:* {broadcast_text[:100]}...\n\n"
                    f"This will be sent to ALL users. Continue?",
                    parse_mode="Markdown",
                    reply_markup=markup)

# ========= CALLBACK QUERY HANDLER =========
@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    if call.data == "cancel_broadcast":
        bot.edit_message_text("❌ Broadcast cancelled.",
                            call.message.chat.id,
                            call.message.message_id)
        return
    
    if call.data.startswith("confirm_broadcast:"):
        broadcast_text = call.data.split(':', 1)[1]
        
        # Update message to show sending status
        bot.edit_message_text("📤 Sending broadcast to all users...",
                            call.message.chat.id,
                            call.message.message_id)
        
        # Get all active users
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT user_id FROM users WHERE is_banned=0")
        users = cur.fetchall()
        conn.close()
        
        total_users = len(users)
        sent_count = 0
        failed_count = 0
        
        # Send to each user
        for (user_id,) in users:
            try:
                bot.send_message(user_id,
                                f"📢 *ANNOUNCEMENT*\n\n{broadcast_text}\n\n"
                                f"_This is a broadcast message from SideHustle Bot_",
                                parse_mode="Markdown")
                sent_count += 1
                time.sleep(0.1)  # Small delay to avoid rate limiting
            except:
                failed_count += 1
        
        # Send report to admin
        bot.send_message(call.message.chat.id,
                        f"✅ *BROADCAST COMPLETE*\n\n"
                        f"*Total Users:* {total_users}\n"
                        f"*Successfully Sent:* {sent_count}\n"
                        f"*Failed:* {failed_count}\n\n"
                        f"*Message:* {broadcast_text[:100]}...",
                        parse_mode="Markdown")
        
        # Log broadcast
        log_activity(call.from_user.id, "broadcast_sent", 
                    f"Sent to {sent_count} users. Message: {broadcast_text[:50]}")

# ========= UNKNOWN COMMAND HANDLER =========
@bot.message_handler(func=lambda message: True)
def handle_unknown(message):
    user_id = message.from_user.id
    
    # Log unknown command
    log_activity(user_id, "unknown_command", message.text[:50])
    
    # Check if it's a text message (not command)
    if not message.text.startswith('/'):
        return
    
    bot.send_message(message.chat.id,
                    "❓ *Unknown Command*\n\n"
                    "Available commands:\n"
                    "/start - Start the bot\n"
                    "/jobs - Browse jobs\n"
                    "/profile - View profile\n"
                    "/help - Get help\n"
                    "/getid - Get your Telegram ID",
                    parse_mode="Markdown")

# ========= MAIN FUNCTION =========
def main():
    print("=" * 50)
    print("🚀 SIDEHUSTLE BOT v4.0 - RAILWAY EDITION")
    print("=" * 50)
    
    # Test environment variables
    print(f"✅ BOT_TOKEN: {'Set' if BOT_TOKEN else 'NOT SET!'}")
    print(f"✅ ADMIN_ID: {ADMIN_ID if ADMIN_ID else 'Not set (admin features disabled)'}")
    
    # Run initial metrics update
    update_daily_metrics()
    
    print("🤖 Bot starting...")
    print("📊 Monitoring enabled")
    print("⏰ 24/7 Uptime: ACTIVE")
    print("=" * 50)
    
    try:
        # Start polling
        bot.infinity_polling(timeout=60, long_polling_timeout=60)
    except Exception as e:
        print(f"❌ Bot crashed: {e}")
        print("🔄 Restarting in 10 seconds...")
        time.sleep(10)
        main()  # Auto-restart

if __name__ == "__main__":
    main()
