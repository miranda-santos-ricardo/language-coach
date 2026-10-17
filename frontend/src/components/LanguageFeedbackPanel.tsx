import type { StructuredLanguageFeedback, FeedbackDimension } from "../api/conversations";

const labels: { key: keyof Pick<StructuredLanguageFeedback, "grammar" | "vocabulary" | "clarity" | "naturalness" | "register">; title: string }[] = [
  { key: "grammar", title: "Grammar" }, { key: "vocabulary", title: "Vocabulary" },
  { key: "clarity", title: "Clarity" }, { key: "naturalness", title: "Naturalness" },
  { key: "register", title: "Register" },
];
function Dimension({ title, value }: { title: string; value: FeedbackDimension }) {
  return <li><strong>{title}:</strong> {value.status.replaceAll("_", " ")} — {value.explanation}
    {value.suggestion && <p>Suggestion: {value.suggestion}</p>}</li>;
}
export function LanguageFeedbackPanel({ feedback }: { feedback: StructuredLanguageFeedback }) {
  return <details className="conversation-feedback">
    <summary>View language feedback</summary>
    <p>{feedback.overall_assessment}</p>
    <ul>{labels.map(({ key, title }) => <Dimension key={key} title={title} value={feedback[key]} />)}</ul>
    <p><strong>Improved version:</strong> {feedback.improved_version}</p>
    {feedback.explanations.length > 0 && <ul>{feedback.explanations.map((value, index) => <li key={index}>{value}</li>)}</ul>}
    <p><strong>Strengths:</strong> {feedback.strengths.join("; ")}</p>
    <p><strong>Next practice:</strong> {feedback.next_recommendation}</p>
  </details>;
}
