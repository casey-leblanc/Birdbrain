"""Schools Birdbrain knows the addresses of, so a student there has nothing to type on first run.

Choosing one on the welcome page fills in where Moodle and Outlook are. "Another school" asks for them instead.
Birdbrain is a student project and is not affiliated with any school listed here.
"""
SCHOOLS = {
    "lsu": {"name": "LSU", "full": "Louisiana State University", "moodle": "https://moodle.lsu.edu",
            "outlook": "https://outlook.office.com",
            "says": "Moodle at moodle.lsu.edu, and your LSU email in Outlook. Nothing to type."},
}
DEFAULT = "lsu"
