class StatusPriority:
    # Scale: Higher number = Higher priority (wins update)
    PRIORITY_MAP = {
        "Applied": 10,
        "Screening": 20,
        "Assessment": 30,
        "Interview": 40,
        "Interview (R1)": 41,
        "Interview (R2)": 42,
        "Interview (Final)": 43,
        "Offer": 50,
        
        # Exceptions logic:
        # Rejected usually shouldn't be overridden by 'Applied' (e.g. automated rejection email delayed)
        # But if you re-apply later? For now, we assume "Rejected" > "Applied".
        "Rejected": 90, 
        "Hired": 100
    }

    @classmethod
    def get_priority(cls, status: str) -> int:
        norm = cls.normalize(status)
        # Default to lowest priority if unknown, so known statuses overwrite it
        return cls.PRIORITY_MAP.get(norm, 0)

    @classmethod
    def should_update(cls, current_status: str, new_status: str) -> bool:
        """
        Returns True if new_status should overwrite current_status.
        Rule: Highest priority wins.
        """
        if not current_status:
            return True
            
        curr_p = cls.get_priority(current_status)
        new_p = cls.get_priority(new_status)
        
        # If new priority is strictly higher, update.
        # If equal, we might assume "latest wins" depending on context, 
        # but for safety in async streams, we usually stick with what we have unless strictly better.
        # Exception: moving FROM 'Applied' TO 'Applied' (duplicate) -> no change.
        return new_p > curr_p

    @staticmethod
    def normalize(status: str) -> str:
        s = status.strip().title()
        # Simple keywords mapping
        if "Reject" in s: return "Rejected"
        if "Offer" in s: return "Offer"
        if "Interview" in s or "Schedule" in s: return "Interview"
        if "Screening" in s: return "Screening"
        if "Assess" in s: return "Assessment"
        return s
