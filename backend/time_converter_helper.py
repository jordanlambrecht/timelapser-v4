# Quick fix: Simple time field conversion without complex validators

from datetime import time

def convert_time_field(value):
    """Simple function to convert time objects to strings"""
    if value is None:
        return None
    if isinstance(value, time):
        return value.strftime('%H:%M')
    if isinstance(value, str):
        return value
    return str(value)

# You can use this in a simpler model definition or in the database query
print("Use this function to convert time fields manually if needed")
