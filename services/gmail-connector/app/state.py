import json
import os
from typing import Dict, Optional
from pathlib import Path

class StateManager:
    """
    Manages user state and sync locks
    NO email data persists across account switch
    """
    
    def __init__(self, state_dir: str = "/app/state"):
        self.state_dir = Path(state_dir)
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.locks: Dict[str, Dict] = {}
    
    def get_user_state(self, user_id: str) -> Dict:
        """
        Get user state from file
        """
        state_file = self.state_dir / f"{user_id}.json"
        
        if not state_file.exists():
            return {"applications": []}
        
        try:
            with open(state_file, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error reading state: {e}")
            return {"applications": []}
    
    def save_user_state(self, user_id: str, state: Dict):
        """
        Save user state to file
        """
        state_file = self.state_dir / f"{user_id}.json"
        
        try:
            with open(state_file, 'w') as f:
                json.dump(state, f, indent=2)
        except Exception as e:
            print(f"Error saving state: {e}")
    
    def clear_user_state(self, user_id: str):
        """
        Clear all cached email data for user
        Called on logout or account switch
        """
        state_file = self.state_dir / f"{user_id}.json"
        
        if state_file.exists():
            try:
                state_file.unlink()
            except Exception as e:
                print(f"Error clearing state: {e}")
        
        # Clear lock
        self.release_lock(user_id)
    
    def set_lock(self, user_id: str, job_id: str, reason: str):
        """
        Set sync lock to prevent concurrent syncs
        """
        self.locks[user_id] = {
            "job_id": job_id,
            "reason": reason,
        }
    
    def get_lock(self, user_id: str) -> Optional[Dict]:
        """
        Get sync lock info
        """
        return self.locks.get(user_id)
    
    def release_lock(self, user_id: str):
        """
        Release sync lock
        Locks are released on service restart
        """
        if user_id in self.locks:
            del self.locks[user_id]
