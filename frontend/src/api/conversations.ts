import { apiRequest } from "./client";

export type InputModality = "text" | "voice";
export type FeedbackStatus = "correct" | "improvement_possible" | "incorrect" | "not_applicable";
export interface FeedbackDimension {
  status: FeedbackStatus;
  explanation: string;
  suggestion: string | null;
}
export interface StructuredLanguageFeedback {
  overall_assessment: string;
  grammar: FeedbackDimension;
  vocabulary: FeedbackDimension;
  clarity: FeedbackDimension;
  naturalness: FeedbackDimension;
  register: FeedbackDimension;
  improved_version: string;
  explanations: string[];
  strengths: string[];
  next_recommendation: string;
}
export interface TurnSubmission {
  text: string;
  input_modality: InputModality;
  client_request_id: string;
}
export interface TurnSubmitted {
  turn_id: string;
  turn_index: number;
  coach_response: string;
  feedback: StructuredLanguageFeedback;
  replayed: boolean;
  prompt_version: string | null;
  model: string | null;
}
export interface ConversationTurnDetail {
  turn_id: string;
  turn_index: number;
  input_modality: InputModality;
  learner_text: string;
  coach_response: string;
  created_at: string;
  feedback: StructuredLanguageFeedback;
}
export interface ConversationTurnPage {
  items: ConversationTurnDetail[];
  limit: number;
  offset: number;
}
export interface ConversationContextIds {
  userId: string;
  profileId: string;
  sessionId: string;
}
function turnsPath({ userId, profileId, sessionId }: ConversationContextIds) {
  return `/users/${encodeURIComponent(userId)}/language-profiles/${encodeURIComponent(profileId)}/sessions/${encodeURIComponent(sessionId)}/turns`;
}
export const conversationsApi = {
  submit(context: ConversationContextIds, payload: TurnSubmission) {
    return apiRequest<TurnSubmitted>(turnsPath(context), {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },
  list(context: ConversationContextIds, limit = 50, offset = 0) {
    return apiRequest<ConversationTurnPage>(`${turnsPath(context)}?limit=${limit}&offset=${offset}`);
  },
  get(context: ConversationContextIds, turnId: string) {
    return apiRequest<ConversationTurnDetail>(`${turnsPath(context)}/${encodeURIComponent(turnId)}`);
  },
};
