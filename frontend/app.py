"""
Flask IAM Management Tool
Replaces server.py with Redis-backed policy and log management
"""
from flask import Flask, render_template, jsonify, request, send_from_directory
from flask_cors import CORS
from database import get_db
import os
from typing import Dict, List, Optional

app = Flask(__name__, 
            static_folder='.',
            template_folder='.')
CORS(app)

# Redis connection settings from environment
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6380))

# Initialize database
db = get_db(redis_host=REDIS_HOST, redis_port=REDIS_PORT)

# ========== Static Pages ==========
@app.route('/')
@app.route('/dashboard.html')
def dashboard():
    """Dashboard page"""
    return send_from_directory('.', 'dashboard.html')

@app.route('/agents/agents.html')
def agents_page():
    """Agents management page"""
    return send_from_directory('agents', 'agents.html')

@app.route('/logs/logs.html')
def logs_page():
    """Logs page"""
    return send_from_directory('logs', 'logs.html')

@app.route('/ruleset/ruleset.html')
def ruleset_page():
    """Ruleset management page"""
    return send_from_directory('ruleset', 'ruleset.html')

# Serve CSS files
@app.route('/style.css')
def main_style():
    return send_from_directory('.', 'style.css')

@app.route('/agents/style.css')
def agents_style():
    return send_from_directory('agents', 'style.css')

@app.route('/logs/style.css')
def logs_style():
    return send_from_directory('logs', 'style.css')

@app.route('/ruleset/style.css')
def ruleset_style():
    return send_from_directory('ruleset', 'style.css')

# Serve JS files
@app.route('/dashboard.js')
def dashboard_js():
    return send_from_directory('.', 'dashboard.js')

@app.route('/agents/agents.js')
def agents_js():
    return send_from_directory('agents', 'agents.js')

@app.route('/logs/logs.js')
def logs_js():
    return send_from_directory('logs', 'logs.js')

@app.route('/ruleset/ruleset.js')
def ruleset_js():
    return send_from_directory('ruleset', 'ruleset.js')

# ========== API Endpoints ==========

# --- Dashboard Stats ---
@app.route('/api/stats', methods=['GET'])
def get_stats():
    """Get system statistics"""
    try:
        stats = db.get_stats()
        
        # Get recent violations count (last 24 hours)
        logs = db.get_logs(limit=1000)
        violations = [log for log in logs if log.get('verdict') == 'BLOCKED' or log.get('verdict') == 'VIOLATION']
        
        stats['recent_violations'] = len(violations)
        stats['total_events'] = len(logs)
        
        return jsonify(stats), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# --- Agent Management ---
@app.route('/api/agents', methods=['GET'])
def get_agents():
    """Get all agents"""
    try:
        agents = db.get_all_agents()
        return jsonify(agents), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/agents/<agent_id>', methods=['GET'])
def get_agent(agent_id: str):
    """Get specific agent"""
    try:
        agent = db.get_agent(agent_id)
        if not agent:
            return jsonify({"error": "Agent not found"}), 404
        
        # Include policy information
        policy = db.get_policy_by_agent(agent_id)
        agent['policy'] = policy
        
        return jsonify(agent), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/agents/<agent_id>', methods=['PUT'])
def update_agent(agent_id: str):
    """Update agent"""
    try:
        data = request.json
        success = db.update_agent(agent_id, data)
        
        if success:
            return jsonify({"message": "Agent updated successfully"}), 200
        else:
            return jsonify({"error": "Agent not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/agents/<agent_id>/policy', methods=['PUT'])
def assign_agent_policy(agent_id: str):
    """Assign IAM rulesets to an agent's policy"""
    try:
        data = request.json or {}

        assignments = {
            "prompt_validation_rulesets": data.get('prompt_validation_rulesets', []),
            "tool_validation_rulesets": data.get('tool_validation_rulesets', []),
            "response_filtering_rulesets": data.get('response_filtering_rulesets', [])
        }

        enabled = data.get('enabled')
        if isinstance(enabled, str):
            enabled = enabled.lower() == 'true'

        success = db.assign_rulesets_to_agent(agent_id, assignments, enabled)

        if success:
            return jsonify({"message": "Agent policy updated"}), 200
        return jsonify({"error": "Agent not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/agents', methods=['POST'])
def create_agent():
    """Create new agent"""
    try:
        data = request.json
        success = db.create_agent(data)
        
        if success:
            return jsonify({"message": "Agent created successfully"}), 201
        else:
            return jsonify({"error": "Failed to create agent"}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# --- Ruleset Management ---
@app.route('/api/rulesets', methods=['GET'])
def get_rulesets():
    """Get all rulesets"""
    try:
        rulesets = db.get_all_rulesets()
        return jsonify(rulesets), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/rulesets/<ruleset_id>', methods=['GET'])
def get_ruleset(ruleset_id: str):
    """Get specific ruleset"""
    try:
        ruleset = db.get_ruleset(ruleset_id)
        if not ruleset:
            return jsonify({"error": "Ruleset not found"}), 404
        return jsonify(ruleset), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/rulesets', methods=['POST'])
def create_ruleset():
    """Create new ruleset"""
    try:
        data = request.json
        success = db.create_ruleset(data)
        
        if success:
            return jsonify({"message": "Ruleset created successfully"}), 201
        else:
            return jsonify({"error": "Failed to create ruleset"}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/rulesets/<ruleset_id>', methods=['PUT'])
def update_ruleset(ruleset_id: str):
    """Update ruleset"""
    try:
        data = request.json
        success = db.update_ruleset(ruleset_id, data)
        
        if success:
            return jsonify({"message": "Ruleset updated successfully"}), 200
        else:
            return jsonify({"error": "Ruleset not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/rulesets/<ruleset_id>', methods=['DELETE'])
def delete_ruleset(ruleset_id: str):
    """Delete ruleset"""
    try:
        success = db.delete_ruleset(ruleset_id)
        
        if success:
            return jsonify({"message": "Ruleset deleted successfully"}), 200
        else:
            return jsonify({"error": "Ruleset not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# --- Policy Management ---
@app.route('/api/policies', methods=['GET'])
def get_policies():
    """Get all policies"""
    try:
        policies = db.get_all_policies()
        return jsonify(policies), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/policies/<policy_id>', methods=['GET'])
def get_policy(policy_id: str):
    """Get specific policy"""
    try:
        policy = db.get_policy(policy_id)
        if not policy:
            return jsonify({"error": "Policy not found"}), 404
        return jsonify(policy), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/policies/<policy_id>', methods=['PUT'])
def update_policy(policy_id: str):
    """Update policy"""
    try:
        data = request.json
        success = db.update_policy(policy_id, data)
        
        if success:
            return jsonify({"message": "Policy updated successfully"}), 200
        else:
            return jsonify({"error": "Policy not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/policies', methods=['POST'])
def create_policy():
    """Create new policy"""
    try:
        data = request.json
        success = db.create_policy(data)
        
        if success:
            return jsonify({"message": "Policy created successfully"}), 201
        else:
            return jsonify({"error": "Failed to create policy"}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# --- IAM Policy API (for agents to fetch policies) ---
@app.route('/api/iam/policy/<agent_id>', methods=['GET'])
def get_iam_policy(agent_id: str):
    """Get IAM policy for specific agent (used by agents)"""
    try:
        policy = db.get_policy_by_agent(agent_id)
        
        if not policy:
            return jsonify({"error": f"No policy found for agent: {agent_id}"}), 404
        
        return jsonify(policy), 200
    except Exception as e:
        print(f"[PolicyServer] Error fetching policy for {agent_id}: {e}")
        return jsonify({"error": str(e)}), 500

# --- Legacy system-prompt endpoint (backward compatibility) ---
@app.route('/api/system-prompt', methods=['GET'])
def get_system_prompt():
    """Get system prompt (legacy endpoint for backward compatibility)"""
    try:
        agent_id = request.args.get('agent_id', 'orchestrator')
        policy = db.get_policy_by_agent(agent_id)
        
        if not policy or not policy.get('prompt_validation_rules'):
            return jsonify({"system_prompt": ""}), 200
        
        # Return first prompt validation rule
        first_rule = policy['prompt_validation_rules'][0]
        return jsonify({
            "system_prompt": first_rule.get('system_prompt', ''),
            "model": first_rule.get('model', 'gemini-2.0-flash-exp')
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# --- Log Management ---
@app.route('/api/logs', methods=['GET'])
def get_logs():
    """Get logs with optional filtering"""
    try:
        limit = int(request.args.get('limit', 100))
        agent_id = request.args.get('agent_id')
        
        logs = db.get_logs(limit=limit, agent_id=agent_id)
        return jsonify(logs), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/logs', methods=['POST'])
def add_log():
    """Add new log entry"""
    try:
        log_data = request.json
        success = db.add_log(log_data)
        
        if success:
            return jsonify({"message": "Log added successfully"}), 201
        else:
            return jsonify({"error": "Failed to add log"}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/logs', methods=['DELETE'])
def clear_logs():
    """Clear all logs"""
    try:
        success = db.clear_logs()
        
        if success:
            return jsonify({"message": "Logs cleared successfully"}), 200
        else:
            return jsonify({"error": "Failed to clear logs"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/graph/agent-flow', methods=['GET'])
def get_agent_flow():
    """Return aggregated agent flow data for visualisation"""
    try:
        limit = int(request.args.get('limit', 200))
        flow = db.get_agent_flow(limit=limit)
        return jsonify(flow), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# --- Health Check ---
@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    try:
        # Test Redis connection
        stats = db.get_stats()
        return jsonify({
            "status": "healthy",
            "redis": "connected",
            "stats": stats
        }), 200
    except Exception as e:
        return jsonify({
            "status": "unhealthy",
            "error": str(e)
        }), 503

if __name__ == '__main__':
    port = int(os.getenv('PORT', 8005))
    print(f"Starting IAM Management Server on port {port}")
    print(f"Redis: {REDIS_HOST}:{REDIS_PORT}")
    print(f"Dashboard: http://localhost:{port}/")
    
    app.run(host='0.0.0.0', port=port, debug=True)

