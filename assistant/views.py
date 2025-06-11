# assistant/views.py
import os

# ... (other imports)
from django.shortcuts import render, redirect
from django.conf import settings
from .forms import SubmissionForm
from .services import convert_audio_to_wav, evaluate_pronunciation


def submit_audio(request):
    if request.method == 'POST':
        form = SubmissionForm(request.POST, request.FILES)
        if form.is_valid():
            submission = form.save(commit=False)
            submission.evaluation_status = 'Processing'
            submission.save()

            audio_path = submission.audio_file.path
            processed_audio_path = None
            try:
                processed_audio_path = convert_audio_to_wav(audio_path)
                print(f"Converted audio to: {processed_audio_path}")  # This should print in your server console!

                feedback = evaluate_pronunciation(processed_audio_path, submission.original_text)
                submission.feedback_json = feedback
                if "error" in feedback:
                    submission.evaluation_status = 'Failed'
                else:
                    submission.evaluation_status = 'Completed'

            except Exception as e:
                submission.evaluation_status = 'Failed'
                submission.feedback_json = {"error": f"Audio processing failed: {str(e)}"}
                print(
                    f"Error processing audio for submission {submission.id}: {e}")  # This should print in your server console!
            finally:
                submission.save()
                if processed_audio_path and os.path.exists(processed_audio_path):
                    os.remove(processed_audio_path)

            # THIS IS THE CRUCIAL REDIRECT LINE:
            return redirect('submission_detail', submission_id=submission.id)

    else:
        form = SubmissionForm()
    return render(request, 'assistant/submit_audio.html', {'form': form})
# assistant/views.py
# ... (all your imports and submit_audio function above this)

# New view to display submission details and feedback
def submission_detail(request, submission_id):
    from .models import Submission # Import here to avoid circular dependency issues if any
    try:
        submission = Submission.objects.get(id=submission_id)
    except Submission.DoesNotExist:
        return render(request, 'assistant/submission_not_found.html', status=404)

    return render(request, 'assistant/submission_detail.html', {'submission': submission})

# New view for submission not found
def submission_not_found(request):
    return render(request, 'assistant/submission_not_found.html')
# ... (rest of the views, like submission_detail and submission_not_found)