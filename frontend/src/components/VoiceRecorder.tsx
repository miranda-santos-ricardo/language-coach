import { useEffect, useState } from "react";

import { useAudioRecorder } from "../hooks/useAudioRecorder";

export function VoiceRecorder() {
  const {
    status,
    recordedAudio,
    error,
    startRecording,
    stopRecording,
    reset,
  } = useAudioRecorder();

  const [audioUrl, setAudioUrl] = useState<string | null>(null);

  useEffect(() => {
    if (!recordedAudio) {
      setAudioUrl(null);
      return;
    }

    const url = URL.createObjectURL(recordedAudio.blob);

    setAudioUrl(url);

    return () => {
      URL.revokeObjectURL(url);
    };
  }, [recordedAudio]);

  return (
    <section aria-labelledby="voice-recorder-title">
      <h3 id="voice-recorder-title">Voice practice</h3>

      {status === "IDLE" && (
        <div>
          <p>Record your voice to start practicing.</p>

          <button
            type="button"
            onClick={() => void startRecording()}
          >
            Start recording
          </button>
        </div>
      )}

      {status === "RECORDING" && (
        <div>
          <p role="status">Recording...</p>

          <button
            type="button"
            onClick={stopRecording}
          >
            Stop recording
          </button>
        </div>
      )}

      {status === "RECORDED" && recordedAudio && (
        <div>
          <p role="status">Recording ready.</p>

          {audioUrl && (
            <audio
              controls
              src={audioUrl}
            />
          )}

          <p>
            Format: {recordedAudio.mimeType}
          </p>

          <button
            type="button"
            onClick={reset}
          >
            Record again
          </button>
        </div>
      )}

      {status === "ERROR" && error && (
        <div role="alert">
          <p>{error.message}</p>

          <button
            type="button"
            onClick={reset}
          >
            Try again
          </button>
        </div>
      )}
    </section>
  );
}