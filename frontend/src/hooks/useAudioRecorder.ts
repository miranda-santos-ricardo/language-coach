import {
  useCallback,
  useEffect,
  useRef,
  useState,
} from "react";


export type AudioRecorderStatus =
  | "IDLE"
  | "RECORDING"
  | "RECORDED"
  | "ERROR";

export interface RecordedAudio {
  blob: Blob;
  mimeType: string;
  extension: string;
}

  export type AudioRecorderErrorCode =
  | "INSECURE_CONTEXT"
  | "MICROPHONE_PERMISSION_DENIED"
  | "MICROPHONE_UNAVAILABLE"
  | "MEDIA_RECORDER_UNSUPPORTED"
  | "RECORDING_FAILED";

export interface AudioRecorderError {
  code: AudioRecorderErrorCode;
  message: string;
}





const AUDIO_MIME_CANDIDATES = [
  {
    mimeType: "audio/webm;codecs=opus",
    extension: "webm",
  },
  {
    mimeType: "audio/webm",
    extension: "webm",
  },
  {
    mimeType: "audio/mp4",
    extension: "mp4",
  },
] as const;

export interface SupportedAudioFormat {
  mimeType: string;
  extension: string;
}

export function getSupportedAudioFormat():
  | SupportedAudioFormat
  | null {
  if (typeof MediaRecorder === "undefined") {
    return null;
  }

  for (const candidate of AUDIO_MIME_CANDIDATES) {
    if (MediaRecorder.isTypeSupported(candidate.mimeType)) {
      return candidate;
    }
  }

  return null;
}




export function useAudioRecorder() {
  const [status, setStatus] =
    useState<AudioRecorderStatus>("IDLE");

  const [recordedAudio, setRecordedAudio] =
    useState<RecordedAudio | null>(null);

  const [error, setError] =
    useState<AudioRecorderError | null>(null);

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const mediaStreamRef = useRef<MediaStream | null>(null);
  const chunksRef = useRef<Blob[]>([]);

  const releaseMicrophone = useCallback(() => {
    mediaStreamRef.current?.getTracks().forEach((track) => {
      track.stop();
    });

    mediaStreamRef.current = null;
  }, []);

  const reset = useCallback(() => {
    if (mediaRecorderRef.current?.state === "recording") {
      mediaRecorderRef.current.stop();
    }

    releaseMicrophone();

    mediaRecorderRef.current = null;
    chunksRef.current = [];

    setRecordedAudio(null);
    setError(null);
    setStatus("IDLE");
  }, [releaseMicrophone]);

  const startRecording = useCallback(async () => {
    setError(null);
    setRecordedAudio(null);

    if (
      typeof window !== "undefined" &&
      !window.isSecureContext
    ) {
      setError({
        code: "INSECURE_CONTEXT",
        message:
          "Microphone recording requires a secure browser context.",
      });

      setStatus("ERROR");
      return;
    }

    if (
      typeof navigator === "undefined" ||
      !navigator.mediaDevices?.getUserMedia
    ) {
      setError({
        code: "MICROPHONE_UNAVAILABLE",
        message: "Microphone access is not available in this browser.",
      });
      setStatus("ERROR");
      return;
    }

    if (typeof MediaRecorder === "undefined") {
      setError({
        code: "MEDIA_RECORDER_UNSUPPORTED",
        message: "Audio recording is not supported in this browser.",
      });
      setStatus("ERROR");
      return;
    }

    const format = getSupportedAudioFormat();

    if (!format) {
      setError({
        code: "MEDIA_RECORDER_UNSUPPORTED",
        message: "No supported audio recording format was found.",
      });
      setStatus("ERROR");
      return;
    }

    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: true,
      });

      mediaStreamRef.current = stream;
      chunksRef.current = [];

      const recorder = new MediaRecorder(stream, {
        mimeType: format.mimeType,
      });

      mediaRecorderRef.current = recorder;

      recorder.ondataavailable = (event: BlobEvent) => {
        if (event.data.size > 0) {
          chunksRef.current.push(event.data);
        }
      };

      recorder.onstop = () => {
        const blob = new Blob(chunksRef.current, {
          type: format.mimeType,
        });

        chunksRef.current = [];

        releaseMicrophone();

        if (blob.size === 0) {
          setRecordedAudio(null);
          setError({
            code: "RECORDING_FAILED",
            message: "The audio recording is empty.",
          });
          setStatus("ERROR");
          return;
        }

        setRecordedAudio({
          blob,
          mimeType: format.mimeType,
          extension: format.extension,
        });

        setStatus("RECORDED");
      };

      recorder.onerror = () => {
        releaseMicrophone();

        setRecordedAudio(null);
        setError({
          code: "RECORDING_FAILED",
          message: "The audio recording failed.",
        });
        setStatus("ERROR");
      };

      recorder.start();

      setStatus("RECORDING");
    } catch (recordingError) {
      releaseMicrophone();

      if (
        recordingError instanceof DOMException &&
        (
          recordingError.name === "NotAllowedError" ||
          recordingError.name === "SecurityError"
        )
      ) {
        setError({
          code: "MICROPHONE_PERMISSION_DENIED",
          message: "Microphone permission was denied.",
        });
      } else {
        setError({
          code: "MICROPHONE_UNAVAILABLE",
          message: "The microphone could not be accessed.",
        });
      }

      setStatus("ERROR");
    }
  }, [releaseMicrophone]);

  const stopRecording = useCallback(() => {
    const recorder = mediaRecorderRef.current;

    if (!recorder || recorder.state !== "recording") {
      return;
    }

    recorder.stop();
  }, []);

  useEffect(() => {
    return () => {
      const recorder = mediaRecorderRef.current;

      if (recorder?.state === "recording") {
        recorder.stop();
      }

      releaseMicrophone();
    };
  }, [releaseMicrophone]);

  return {
    status,
    recordedAudio,
    error,
    startRecording,
    stopRecording,
    reset,
  };
}