# # assistant/services.py
#
# import os
# import json
# import time  # For polling operations
# from pydub import AudioSegment
# from pydub.exceptions import CouldntDecodeError
# from google.cloud import speech_v1p1beta1 as speech
# from google.cloud import storage  # NEW IMPORT for Google Cloud Storage
# from django.conf import settings
# from fuzzywuzzy import process
#
# # --- Configuration for Google Cloud Credentials ---
# os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = os.path.join(settings.BASE_DIR, 'google-credentials.json')
#
#
# def convert_audio_to_wav(audio_file_path):
#     """
#     Converts an audio file to WAV format (mono, 16kHz, 16-bit PCM).
#     This function remains largely the same.
#     """
#     output_path = audio_file_path + ".wav"
#     try:
#         audio = AudioSegment.from_file(audio_file_path)
#         audio = audio.set_channels(1).set_frame_rate(16000).set_sample_width(2)
#         audio.export(output_path, format="wav")
#         print(f"Successfully converted '{audio_file_path}' to '{output_path}'")
#         return output_path
#     except CouldntDecodeError as e:
#         print(f"Error decoding audio file {audio_file_path}: {e}")
#         raise ValueError(
#             f"Could not decode audio file. "
#             f"Please ensure FFmpeg is installed and accessible in your system's PATH. Error: {e}"
#         )
#     except Exception as e:
#         print(f"An unexpected error occurred during audio conversion of '{audio_file_path}': {e}")
#         raise
#
#
# def upload_to_gcs(local_file_path, destination_blob_name):
#     """
#     Uploads a file to a Google Cloud Storage bucket.
#
#     Args:
#         local_file_path (str): The path to the local file to upload.
#         destination_blob_name (str): The desired name of the blob (file) in GCS.
#
#     Returns:
#         str: The Google Cloud Storage URI (gs://bucket-name/blob-name) of the uploaded file.
#     """
#     try:
#         storage_client = storage.Client()
#         bucket = storage_client.bucket(settings.GCS_BUCKET_NAME)
#         blob = bucket.blob(destination_blob_name)
#
#         blob.upload_from_filename(local_file_path)
#         print(f"File {local_file_path} uploaded to {destination_blob_name} in bucket {settings.GCS_BUCKET_NAME}.")
#         return f"gs://{settings.GCS_BUCKET_NAME}/{destination_blob_name}"
#     except Exception as e:
#         print(f"Error uploading file to GCS: {e}")
#         raise
#
#
# def evaluate_pronunciation(audio_file_path, original_text):
#     """
#     Performs Speech-to-Text transcription and basic pronunciation evaluation
#     using Google Cloud Speech-to-Text API's LongRunningRecognize for longer audio.
#
#     Args:
#         audio_file_path (str): The path to the pre-processed (WAV) audio file.
#                                 This file will be uploaded to GCS.
#         original_text (str): The text the student was supposed to read.
#
#     Returns:
#         dict: A dictionary containing transcription, word-by-word feedback,
#               an overall score, and a summary. Includes an 'error' key if
#               an issue occurs during API call.
#     """
#     client = speech.SpeechClient()
#
#     feedback = {
#         "transcription": "",
#         "words_feedback": [],
#         "overall_score": None,
#         "summary": ""
#     }
#
#     gcs_uri = None  # Initialize GCS URI variable
#     try:
#         # 1. Upload audio file to Google Cloud Storage
#         # Use a unique name for the blob to avoid conflicts
#         gcs_blob_name = f"student_audio/{os.path.basename(audio_file_path)}_{int(time.time())}.wav"
#         gcs_uri = upload_to_gcs(audio_file_path, gcs_blob_name)
#
#         audio = speech.RecognitionAudio(uri=gcs_uri)  # Use URI instead of content
#
#         config = speech.RecognitionConfig(
#             encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
#             sample_rate_hertz=16000,
#             language_code="en-US",
#             enable_automatic_punctuation=True,
#             enable_word_time_offsets=True,
#             enable_word_confidence=True
#         )
#
#         # Use LongRunningRecognize for asynchronous processing
#         operation = client.long_running_recognize(config=config, audio=audio)
#
#         print(f"LongRunningRecognize operation started: {operation}")
#
#         # Wait for the operation to complete (blocking call for now, will be async later)
#         # In a real app with Celery, this 'result()' call would be in a background task.
#         # For synchronous testing, we'll wait here.
#         # Add a timeout to prevent infinite waits in case of API issues
#         response = operation.result(timeout=300)  # Wait up to 5 minutes for results
#
#         if response.results:
#             result = response.results[0]
#             transcribed_text = result.alternatives[0].transcript
#             transcribed_words_details = result.alternatives[0].words
#
#             feedback["transcription"] = transcribed_text
#
#             original_words_raw = original_text.lower()
#             for char in ['.', ',', '!', '?', ':', ';', '"', "'", '(', ')', '[', ']', '{', '}']:
#                 original_words_raw = original_words_raw.replace(char, '')
#             original_words_list = original_words_raw.split()
#
#             detailed_feedback_list = []
#             matched_transcribed_indices = set()
#             correctly_pronounced_words = 0
#
#             for i, original_word in enumerate(original_words_list):
#                 best_match = None
#                 best_score = -1
#                 best_index = -1
#
#                 for j, transcribed_detail in enumerate(transcribed_words_details):
#                     if j not in matched_transcribed_indices:
#                         match_result = process.extractOne(original_word, [transcribed_detail.word.lower()],
#                                                           score_cutoff=70)
#                         if match_result and match_result[1] > best_score:
#                             best_score = match_result[1]
#                             best_match = transcribed_detail
#                             best_index = j
#
#                 word_info = {
#                     "expected_word": original_word,
#                     "transcribed_word": None,
#                     "confidence": None,
#                     "is_mispronounced": True,
#                     "reason": "Word skipped or severely mispronounced"
#                 }
#
#                 if best_match:
#                     word_info["transcribed_word"] = best_match.word
#                     word_info["confidence"] = best_match.confidence
#                     word_info["start_time"] = best_match.start_time.total_seconds()
#                     word_info["end_time"] = best_match.end_time.total_seconds()
#                     matched_transcribed_indices.add(best_index)
#
#                     if best_score >= 90 and best_match.confidence >= 0.85:
#                         word_info["is_mispronounced"] = False
#                         word_info["reason"] = "Pronounced correctly"
#                         correctly_pronounced_words += 1
#                     elif best_score >= 70 and best_match.confidence >= 0.60:
#                         word_info["is_mispronounced"] = True
#                         word_info[
#                             "reason"] = f"Low confidence ({best_match.confidence:.2f}) or partial match (score {best_score}): potentially unclear pronunciation"
#                     else:
#                         word_info["is_mispronounced"] = True
#                         word_info[
#                             "reason"] = f"Poor match (score {best_score}) or very low confidence ({best_match.confidence:.2f}): likely mispronounced"
#
#                 detailed_feedback_list.append(word_info)
#
#             for j, transcribed_detail in enumerate(transcribed_words_details):
#                 if j not in matched_transcribed_indices:
#                     detailed_feedback_list.append({
#                         "expected_word": None,
#                         "transcribed_word": transcribed_detail.word,
#                         "confidence": transcribed_detail.confidence,
#                         "is_mispronounced": True,
#                         "reason": "Extra word spoken (not in original text)",
#                         "start_time": transcribed_detail.start_time.total_seconds(),
#                         "end_time": transcribed_detail.end_time.total_seconds()
#                     })
#
#             detailed_feedback_list.sort(key=lambda x: x.get('start_time', 0))
#             feedback["words_feedback"] = detailed_feedback_list
#
#             if original_words_list:
#                 overall_score_percentage = (correctly_pronounced_words / len(original_words_list)) * 100
#                 feedback["overall_score"] = round(overall_score_percentage, 2)
#
#                 feedback["summary"] = (
#                     f"Overall, you pronounced {correctly_pronounced_words} out of {len(original_words_list)} "
#                     f"expected words clearly. Your score is {feedback['overall_score']}%. "
#                 )
#
#                 if overall_score_percentage >= 90:
#                     feedback["summary"] += "Excellent pronunciation! Keep up the great work."
#                 elif overall_score_percentage >= 70:
#                     feedback["summary"] += "Good effort! Review the words highlighted below for improvement."
#                 else:
#                     feedback["summary"] += "Keep practicing! Pay close attention to the suggested words."
#             else:
#                 feedback[
#                     "summary"] = "No original text provided for comparison, so an overall score cannot be calculated."
#
#         else:
#             feedback["transcription"] = "No speech detected or could not transcribe."
#             feedback[
#                 "summary"] = "Could not detect any speech in the audio. Please try recording again, speaking clearly and close to the microphone."
#
#         return feedback
#
#     except Exception as e:
#         print(f"Error during Google Cloud Speech API call or GCS operation: {e}")
#         return {
#             "error": str(e),
#             "transcription": "",
#             "words_feedback": [],
#             "overall_score": None,
#             "summary": "An error occurred during evaluation. Please try again."
#         }
#     finally:
#         # Clean up the audio file from Google Cloud Storage after processing
#         if gcs_uri:
#             try:
#                 storage_client = storage.Client()
#                 bucket_name = gcs_uri.split('/')[2]
#                 blob_name = '/'.join(gcs_uri.split('/')[3:])
#                 bucket = storage_client.bucket(bucket_name)
#                 blob = bucket.blob(blob_name)
#                 blob.delete()
#                 print(f"Cleaned up GCS object: {gcs_uri}")
#             except Exception as cleanup_e:
#                 print(f"Error cleaning up GCS object {gcs_uri}: {cleanup_e}")

# assistant/services.py

import os
import json
import time  # Used for generating unique filenames based on timestamp
from pydub import AudioSegment
from pydub.exceptions import CouldntDecodeError
from google.cloud import speech_v1p1beta1 as speech  # Google Cloud Speech-to-Text API
from google.cloud import storage  # Google Cloud Storage API
from django.conf import settings  # Django settings to access BASE_DIR and GCS_BUCKET_NAME
from fuzzywuzzy import process  # For string matching/alignment in scripted evaluation

# --- Google Cloud Authentication Configuration ---
# This line tells the Google Cloud client library where to find your service account key.
# The 'google-credentials.json' file MUST be in your project's root directory (next to manage.py).
# IMPORTANT: DO NOT commit this file to your Git repository due to security reasons.
# Ensure 'google-credentials.json' is listed in your .gitignore file.
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = os.path.join(settings.BASE_DIR, 'google-credentials.json')


def convert_audio_to_wav(audio_file_path):
    """
    Converts an audio file from various formats (e.g., OGG, MP3, M4A) to
    a standard WAV format (mono, 16kHz sample rate, 16-bit PCM).
    This conversion is crucial because Google Cloud Speech-to-Text API
    prefers specific audio encodings for optimal performance and compatibility.

    Args:
        audio_file_path (str): The absolute path to the input audio file
                                (e.g., a student's uploaded recording).

    Returns:
        str: The absolute path to the newly created WAV file.

    Raises:
        ValueError: If `pydub` cannot decode the audio file, often due to
                    missing FFmpeg installation or a corrupt input file.
        Exception: For any other unexpected errors during the conversion process.
    """
    output_path = audio_file_path + ".wav"
    try:
        # Load audio from the specified file path. pydub intelligently detects the format.
        audio = AudioSegment.from_file(audio_file_path)

        # Standardize audio for Google Speech API:
        # 1. set_channels(1): Convert to mono (single audio channel).
        # 2. set_frame_rate(16000): Resample to 16kHz, which is optimal for speech recognition.
        # 3. set_sample_width(2): Convert to 16-bit PCM (Linear16 encoding).
        audio = audio.set_channels(1).set_frame_rate(16000).set_sample_width(2)

        # Export the processed audio to the new WAV file.
        audio.export(output_path, format="wav")
        print(f"Successfully converted '{audio_file_path}' to '{output_path}'.")
        return output_path
    except CouldntDecodeError as e:
        # This specific error usually means FFmpeg is not installed/configured correctly
        # or the input audio file is truly malformed.
        print(f"Error decoding audio file '{audio_file_path}': {e}")
        raise ValueError(
            f"Could not decode audio file. "
            f"Please ensure FFmpeg is installed and accessible in your system's PATH. "
            f"Detailed error: {e}"
        )
    except Exception as e:
        # Catch any other unexpected errors during audio processing.
        print(f"An unexpected error occurred during audio conversion of '{audio_file_path}': {e}")
        raise


def upload_to_gcs(local_file_path, destination_blob_name):
    """
    Uploads a local file to a specified Google Cloud Storage (GCS) bucket.
    This is necessary for audio files longer than 1 minute when using
    Google Cloud Speech-to-Text's LongRunningRecognize method.

    Args:
        local_file_path (str): The absolute path to the local file to be uploaded.
        destination_blob_name (str): The desired full path/name of the object
                                     within the GCS bucket (e.g., 'audio_uploads/my_file.wav').

    Returns:
        str: The Google Cloud Storage URI (gs://bucket-name/blob-name) of the uploaded file.
             This URI is then passed to the Speech-to-Text API.

    Raises:
        Exception: If any error occurs during the GCS upload process (e.g., permissions, network).
    """
    try:
        # Initialize a GCS client using the credentials configured in GOOGLE_APPLICATION_CREDENTIALS.
        storage_client = storage.Client()

        # Get a reference to the specific bucket using its name from Django settings.
        bucket = storage_client.bucket(settings.GCS_BUCKET_NAME)

        # Create a blob (object) reference within the bucket.
        blob = bucket.blob(destination_blob_name)

        # Upload the file from the local path to the GCS blob.
        blob.upload_from_filename(local_file_path)
        print(
            f"File '{local_file_path}' uploaded to GCS bucket '{settings.GCS_BUCKET_NAME}' as '{destination_blob_name}'.")

        # Return the GCS URI format required by Google Speech-to-Text API.
        return f"gs://{settings.GCS_BUCKET_NAME}/{destination_blob_name}"
    except Exception as e:
        print(f"Error uploading file to GCS: {e}")
        # Re-raise the exception to be caught by the calling function (evaluate_pronunciation)
        raise


def evaluate_pronunciation(audio_file_path, original_text=None):
    """
    Performs Speech-to-Text transcription and flexible pronunciation evaluation.
    The evaluation method adapts based on whether an 'original_text' (script) is provided.

    For audio longer than 1 minute, it utilizes Google Cloud Speech-to-Text's
    LongRunningRecognize method, which requires the audio to be stored in GCS.

    Args:
        audio_file_path (str): The absolute path to the pre-processed (WAV) audio file.
                               This file will be uploaded to GCS for the API call.
        original_text (str, optional): The text the student was supposed to read.
                                       If provided, a 'scripted' evaluation is performed.
                                       If None or empty, a 'free-form' evaluation is performed.
                                       Defaults to None.

    Returns:
        dict: A structured dictionary containing:
              - "transcription": The full text transcribed from the audio.
              - "words_feedback": A list of dictionaries with word-level analysis.
              - "overall_score": A numerical score (percentage) reflecting pronunciation quality.
              - "summary": A textual summary of the evaluation.
              - "evaluation_type": Indicates "scripted" or "free_form" evaluation.
              - "error": Present if an error occurred during processing.
    """
    client = speech.SpeechClient()  # Initialize Google Cloud Speech-to-Text client.

    # Initialize feedback dictionary with default values.
    feedback = {
        "transcription": "",
        "words_feedback": [],
        "overall_score": None,
        "summary": "",
        # Determine initial evaluation type based on original_text presence
        "evaluation_type": "scripted" if original_text and original_text.strip() else "free_form"
    }

    gcs_uri = None  # Variable to store the GCS URI of the uploaded audio.
    try:
        # 1. Prepare and Upload Audio to Google Cloud Storage
        # Generate a unique blob name using the original filename and a timestamp
        gcs_blob_name = f"student_audio/{os.path.basename(audio_file_path)}_{int(time.time())}.wav"
        gcs_uri = upload_to_gcs(audio_file_path, gcs_blob_name)

        # Configure the audio source for the Speech-to-Text API using the GCS URI.
        audio = speech.RecognitionAudio(uri=gcs_uri)

        # Configure the recognition request for the API.
        config = speech.RecognitionConfig(
            encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,  # Our WAV conversion uses this.
            sample_rate_hertz=16000,  # Our WAV conversion uses this.
            language_code="en-US",  # Specify the language (e.g., "en-US", "en-GB").
            enable_automatic_punctuation=True,  # Improves transcription readability.
            enable_word_time_offsets=True,  # Crucial for getting start/end times of words.
            enable_word_confidence=True  # Essential for pronunciation feedback.
        )

        # Use LongRunningRecognize for asynchronous processing of potentially long audio.
        operation = client.long_running_recognize(config=config, audio=audio)
        print(f"LongRunningRecognize operation started: {operation}")  # Log the operation object.

        # Blocking call: Wait for the asynchronous operation to complete.
        # In a real production system, this would be handled by a background task queue (e.g., Celery)
        # to avoid blocking the web server. The web server would return a "processing" status,
        # and the results would be updated later.
        response = operation.result(timeout=300)  # Wait up to 5 minutes for results.

        # Process the API response.
        if response.results:
            result = response.results[0]  # Get the most confident transcription alternative.
            transcribed_text = result.alternatives[0].transcript
            transcribed_words_details = result.alternatives[0].words

            feedback["transcription"] = transcribed_text  # Store the full transcription.

            detailed_feedback_list = []

            # --- Conditional Evaluation Logic ---
            # If original_text is provided, perform scripted evaluation (comparison).
            # Otherwise, perform free-form evaluation (clarity/confidence).
            if original_text and original_text.strip():
                # --- Scripted Evaluation Mode ---
                feedback["evaluation_type"] = "scripted"
                correctly_pronounced_words = 0

                # Clean and split the original text into words for comparison.
                original_words_raw = original_text.lower()
                for char in ['.', ',', '!', '?', ':', ';', '"', "'", '(', ')', '[', ']', '{', '}']:
                    original_words_raw = original_words_raw.replace(char, '')
                original_words_list = original_words_raw.split()

                matched_transcribed_indices = set()  # To track which transcribed words have been matched.

                # First Pass: Attempt to align each original word with a transcribed word.
                for i, original_word in enumerate(original_words_list):
                    best_match = None
                    best_score = -1
                    best_index = -1

                    # Iterate through available (unmatched) transcribed words to find the best match.
                    for j, transcribed_detail in enumerate(transcribed_words_details):
                        if j not in matched_transcribed_indices:
                            # Use fuzzywuzzy to get a similarity score between original and transcribed word.
                            # `score_cutoff` (70) ensures we only consider reasonably similar words.
                            match_result = process.extractOne(original_word, [transcribed_detail.word.lower()],
                                                              score_cutoff=70)
                            if match_result and match_result[1] > best_score:
                                best_score = match_result[1]
                                best_match = transcribed_detail
                                best_index = j

                    word_info = {
                        "expected_word": original_word,  # The word from the script.
                        "transcribed_word": None,
                        "confidence": None,
                        "is_issue": True,  # Assume an issue (skipped/mispronounced) until proven otherwise.
                        "reason": "Word skipped or severely mispronounced"  # Default reason.
                    }

                    if best_match:  # If a match (even partial) was found for the original word.
                        word_info["transcribed_word"] = best_match.word
                        word_info["confidence"] = best_match.confidence
                        # Use .total_seconds() for accurate time values (from Duration objects).
                        word_info["start_time"] = best_match.start_time.total_seconds()
                        word_info["end_time"] = best_match.end_time.total_seconds()
                        matched_transcribed_indices.add(best_index)  # Mark this transcribed word as used.

                        # Determine if the word was pronounced correctly based on match score and confidence.
                        if best_score >= 90 and best_match.confidence >= 0.85:
                            word_info["is_issue"] = False
                            word_info["reason"] = "Pronounced correctly"
                            correctly_pronounced_words += 1
                        elif best_score >= 70 and best_match.confidence >= 0.60:
                            word_info["is_issue"] = True
                            word_info["reason"] = (
                                f"Low confidence ({best_match.confidence:.2f}) or partial match (score {best_score}): "
                                f"potentially unclear pronunciation."
                            )
                        else:
                            word_info["is_issue"] = True
                            word_info["reason"] = (
                                f"Poor match (score {best_score}) or very low confidence ({best_match.confidence:.2f}): "
                                f"likely mispronounced."
                            )

                    detailed_feedback_list.append(word_info)

                # Second Pass: Identify any "extra" words spoken by the student (not in the original script).
                for j, transcribed_detail in enumerate(transcribed_words_details):
                    if j not in matched_transcribed_indices:
                        detailed_feedback_list.append({
                            "expected_word": None,  # Indicates this was an extra word.
                            "transcribed_word": transcribed_detail.word,
                            "confidence": transcribed_detail.confidence,
                            "is_issue": True,  # Extra words are flagged as an issue in scripted mode.
                            "reason": "Extra word spoken (not in original text)",
                            "start_time": transcribed_detail.start_time.total_seconds(),
                            "end_time": transcribed_detail.end_time.total_seconds()
                        })

                # Calculate overall score and summary for scripted evaluation.
                if original_words_list:
                    overall_score_percentage = (correctly_pronounced_words / len(original_words_list)) * 100
                    feedback["overall_score"] = round(overall_score_percentage, 2)

                    feedback["summary"] = (
                        f"Overall, you pronounced {correctly_pronounced_words} out of {len(original_words_list)} "
                        f"expected words clearly. Your score is {feedback['overall_score']}%. "
                    )

                    if overall_score_percentage >= 90:
                        feedback["summary"] += "Excellent pronunciation! Keep up the great work."
                    elif overall_score_percentage >= 70:
                        feedback["summary"] += "Good effort! Review the words highlighted below for improvement."
                    else:
                        feedback["summary"] += "Keep practicing! Pay close attention to the suggested words."
                else:
                    feedback[
                        "summary"] = "No original text was provided for comparison, so a detailed scripted score cannot be calculated."

            else:
                # --- Free-Form Evaluation Mode (No original text provided) ---
                feedback["evaluation_type"] = "free_form"
                total_confidence_sum = 0
                word_count = 0
                low_confidence_words_count = 0

                # Iterate through all transcribed words and assess clarity based on confidence.
                for word_detail in transcribed_words_details:
                    word_info = {
                        "expected_word": None,  # No expected word in free-form.
                        "transcribed_word": word_detail.word,
                        "confidence": word_detail.confidence,
                        "is_issue": False,  # Assume no issue unless confidence is low.
                        "reason": "Clear pronunciation",  # Default reason.
                        "start_time": word_detail.start_time.total_seconds(),
                        "end_time": word_detail.end_time.total_seconds()
                    }

                    # Flag words with low confidence as potential clarity issues.
                    if word_detail.confidence is not None and word_detail.confidence < 0.70:  # Confidence threshold can be tuned.
                        word_info["is_issue"] = True
                        word_info["reason"] = f"Unclear pronunciation (confidence: {word_detail.confidence:.2f})"
                        low_confidence_words_count += 1

                    detailed_feedback_list.append(word_info)

                    if word_detail.confidence is not None:
                        total_confidence_sum += word_detail.confidence
                    word_count += 1

                # Calculate overall score for free-form based on average confidence.
                if word_count > 0:
                    average_confidence = total_confidence_sum / word_count
                    feedback["overall_score"] = round(average_confidence * 100, 2)  # Convert to percentage.

                    feedback["summary"] = (
                        f"Your audio was transcribed as: \"{transcribed_text}\". "
                        f"Your average word clarity score is {feedback['overall_score']}%. "
                    )

                    if feedback["overall_score"] >= 90:
                        feedback["summary"] += "Excellent clarity and fluency! Keep up the great work."
                    elif feedback["overall_score"] >= 70:
                        feedback["summary"] += "Good clarity! Focus on the highlighted words that were less clear."
                    else:
                        feedback["summary"] += "Needs practice on clarity. Review the words marked as unclear."
                else:
                    feedback["summary"] = "No discernible words detected in the audio. Please ensure speech is clear."

            # Sort the aggregated feedback by word start time for chronological display.
            # Handles cases where start_time might be None by placing them at the end.
            detailed_feedback_list.sort(key=lambda x: x.get('start_time', float('inf')))
            feedback["words_feedback"] = detailed_feedback_list

        else:
            # If no results are returned by the Speech-to-Text API.
            feedback["transcription"] = "No speech detected or could not transcribe."
            feedback[
                "summary"] = "Could not detect any speech in the audio. Please try recording again, speaking clearly and close to the microphone."

        return feedback

    except Exception as e:
        # Generic error handling for issues during API calls or GCS operations.
        print(f"Error during Google Cloud Speech API call or GCS operation: {e}")
        return {
            "error": str(e),
            "transcription": "",
            "words_feedback": [],
            "overall_score": None,
            "summary": "An error occurred during evaluation. Please try again.",
            "evaluation_type": "unknown"  # Indicate unknown evaluation type on error.
        }
    finally:
        # --- Clean up the audio file from Google Cloud Storage ---
        # This is important to manage storage costs and keep your bucket tidy.
        if gcs_uri:
            try:
                storage_client = storage.Client()
                # Extract bucket name and blob name from the GCS URI.
                bucket_name = gcs_uri.split('/')[2]
                blob_name = '/'.join(gcs_uri.split('/')[3:])

                bucket = storage_client.bucket(bucket_name)
                blob = bucket.blob(blob_name)
                blob.delete()  # Delete the blob from GCS.
                print(f"Successfully cleaned up GCS object: {gcs_uri}")
            except Exception as cleanup_e:
                # Log any errors during cleanup, but don't re-raise as the primary task is done.
                print(f"Error cleaning up GCS object '{gcs_uri}': {cleanup_e}")

