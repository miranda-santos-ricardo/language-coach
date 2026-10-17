import { useEffect, useState } from "react";

import { api } from "../api/client";
import { useAudioRecorder } from "../hooks/useAudioRecorder";

interface VoiceRecorderProps {
  userId: string;
  profileId: string;
  practiceSessionId: string;
  onUseTranscript?: (text: string) => void;
}

type TranscriptionStatus =
  | "IDLE"
  | "UPLOADING"
  | "SUCCESS"
  | "ERROR";

export function VoiceRecorder({
  userId,
  profileId,
  practiceSessionId,
  onUseTranscript,
}: VoiceRecorderProps) {
  const {
    status,
    recordedAudio,
    error,
    startRecording,
    stopRecording,
    reset,
  } = useAudioRecorder();

  const [audioUrl, setAudioUrl] = useState<string | null>(null);
  const [transcriptionStatus, setTranscriptionStatus] =
    useState<TranscriptionStatus>("IDLE");
  const [transcript, setTranscript] = useState<string | null>(null);
  const [transcriptionError, setTranscriptionError] =
    useState<string | null>(null);

  useEffect(() => {
    if (!recordedAudio) {
      setAudioUrl(null);
      return;
    }

    const url = URL.createObjectURL(recordedAudio.blob);
    setAudioUrl(url);

    return () => URL.revokeObjectURL(url);
  }, [recordedAudio]);

  async function handleTranscribe() {
    if (!recordedAudio || transcriptionStatus === "UPLOADING") {
      return;
    }

    setTranscriptionStatus("UPLOADING");
    setTranscriptionError(null);
    setTranscript(null);

    try {
      const result = await api.transcribeAudio(
        userId,
        profileId,
        practiceSessionId,
        recordedAudio.blob,
        recordedAudio.extension,
      );

      setTranscript(result.transcript);
      setTranscriptionStatus("SUCCESS");
    } catch {
      setTranscriptionError(
        "Unable to transcribe the recording. Please try again.",
      );
      setTranscriptionStatus("ERROR");
    }
  }

  function handleReset() {
    if (transcriptionStatus === "UPLOADING") {
      return;
    }

    reset();
    setTranscript(null);
    setTranscriptionError(null);
    setTranscriptionStatus("IDLE");
  }

  return (
    <section aria-labelledby="voice-recorder-title">
      <h3 id="voice-recorder-title">Voice practice</h3>

      {status === "IDLE" && (
        <div>
          <p>Record your voice to start practicing.</p>
          <button type="button" onClick={() => void startRecording()}>
            Start recording
          </button>
        </div>
      )}

      {status === "RECORDING" && (
        <div>
          <p role="status">Recording...</p>
          <button type="button" onClick={stopRecording}>
            Stop recording
          </button>
        </div>
      )}

      {status === "RECORDED" && recordedAudio && (
        <div>
          <p role="status">Recording ready.</p>

          {audioUrl && <audio controls src={audioUrl} />}

          <p>Format: {recordedAudio.mimeType}</p>

          <button
            type="button"
            onClick={() => void handleTranscribe()}
            disabled={
              transcriptionStatus === "UPLOADING" ||
              transcriptionStatus === "SUCCESS"
            }
          >
            {transcriptionStatus === "UPLOADING"
              ? "Transcribing..."
              : "Transcribe recording"}
          </button>

          <button
            type="button"
            onClick={handleReset}
            disabled={transcriptionStatus === "UPLOADING"}
          >
            Record again
          </button>

          {transcriptionStatus === "UPLOADING" && (
            <p role="status">Uploading and transcribing audio...</p>
          )}

          {transcriptionStatus === "SUCCESS" && transcript && (
            <div aria-label="Transcription result">
              <h4>Transcript</h4>
              <p>{transcript}</p>
              {onUseTranscript && (
                <button type="button" onClick={() => onUseTranscript(transcript)}>
                  Use transcript in coach
                </button>
              )}
            </div>
          )}

          {transcriptionStatus === "ERROR" && (
            <div role="alert">
              <p>{transcriptionError}</p>
            </div>
          )}
        </div>
      )}

      {status === "ERROR" && error && (
        <div role="alert">
          <p>{error.message}</p>
          <button type="button" onClick={handleReset}>
            Try again
          </button>
        </div>
      )}
    </section>
  );
}