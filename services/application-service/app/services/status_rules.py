class StatusPriority:
    PRIORITY_MAP = {
        "Applied": 1,
        "Screening": 2,
        "Interview": 3,
        "Interview_R1": 3,
        "Interview_R2": 4,
        "Interview_Final": 5,
        "Offer": 6,
        "Rejected": 100, # Terminal state usually overrides everything unless it's a re-application
        "Ghosted": 99    # System state
    }

    @classmethod
    def should_update(cls, current_status: str, new_status: str) -> bool:
        """
        Determines if the new status should overwrite the current status based on priority.
        Higher priority value wins.
        """
        if not current_status:
            return True
            
        # Normalize keys
        curr = cls.normalize(current_status)
        new_ = cls.normalize(new_status)
        
        curr_p = cls.PRIORITY_MAP.get(curr, 0)
        new_p = cls.PRIORITY_MAP.get(new_, 0)
        
        # If new status is significantly higher or equal priority (e.g. moving forward)
        # Note: Rejected usually wins over everything unless manually reset
        return new_p > curr_p

    @staticmethod
    def normalize(status: str) -> str:
        # Map various strings to canonical statuses
        s = status.strip().title()
        if "Reject" in s: return "Rejected"
        if "Offer" in s: return "Offer"
        if "Interview" in s: return "Interview"
        return s
