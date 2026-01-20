from collections import defaultdict

sessions = defaultdict(list)

def add_session(user_id, msg):
    sessions[user_id].append(msg)

def get_session(user_id):
    return sessions[user_id]
