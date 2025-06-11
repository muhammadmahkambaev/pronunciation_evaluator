# assistant/models.py
from django.db import models
from django.contrib.auth.models import User # If you want to link to Django's User model

class Submission(models.Model):
    # If you have user authentication, link to the student (Django's default User model)
    # student = models.ForeignKey(User, on_delete=models.CASCADE, related_name='submissions')
    # For now, let's keep it simple without explicit user linking until we add auth.
    student_name = models.CharField(max_length=255, help_text="Name of the student")

    original_text = models.TextField(
        help_text="The text the student was asked to read."
    )
    audio_file = models.FileField(
        upload_to='student_audio/',
        help_text="Uploaded audio recording of the student's reading."
    )
    submitted_at = models.DateTimeField(auto_now_add=True)

    # Fields for future evaluation results
    evaluation_status = models.CharField(
        max_length=50,
        default='Pending',
        help_text="Status of the pronunciation evaluation (e.g., Pending, Processing, Completed, Failed)."
    )
    feedback_json = models.JSONField(
        null=True, blank=True,
        help_text="JSON field to store detailed pronunciation feedback."
    )

    def __str__(self):
        return f"Submission by {self.student_name} on {self.submitted_at.strftime('%Y-%m-%d %H:%M')}"

    class Meta:
        ordering = ['-submitted_at'] # Order by most recent submissions first