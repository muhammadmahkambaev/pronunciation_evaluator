# assistant/forms.py
from django import forms
from .models import Submission

class SubmissionForm(forms.ModelForm):
    class Meta:
        model = Submission
        fields = ['student_name', 'original_text', 'audio_file']
        widgets = {
            'original_text': forms.Textarea(attrs={'rows': 5, 'placeholder': 'Enter the text the student read...'}),
        }