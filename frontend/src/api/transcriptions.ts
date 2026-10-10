export interface TranscriptionResult {
    transcript: string;
    language: string;
}

export interface TranscriptionContext {
    userId: string;
    profileId: string;
    practiceSessionId: string;
}

export async function transcribeAudio(
    context: TranscriptionContext,
    audio: Blob,
    extension: string,
): Promise<TranscriptionResult> {
    const {
        userId,
        profileId,
        practiceSessionId,
    } = context;

    const formData = new FormData();

    const filename = `recording.${extension}`;

    formData.append("file", audio, filename);

    const response = await fetch(
        `/users/${encodeURIComponent(userId)}` +
        `/language-profiles/${encodeURIComponent(profileId)}` +
        `/sessions/${encodeURIComponent(practiceSessionId)}` +
        `/transcriptions`,
        {
        method: "POST",
        body: formData,
        },
    );

    if (!response.ok) {
        throw new Error(
            `Failed to transcribe audio: ${response.status} ${response.statusText}`,
        );
    }

    return (await response.json()) as TranscriptionResult;
}