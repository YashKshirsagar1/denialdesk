import { useState } from "react";

interface OutcomeFormProps {
  caseId: number;
  onOutcomeRecorded: () => void;
}

export function OutcomeForm({ caseId, onOutcomeRecorded }: OutcomeFormProps) {
  const [result, setResult] = useState<"paid" | "partially_paid" | "denied">("paid");
  const [amount, setAmount] = useState("");
  const [paidDate, setPaidDate] = useState("");
  const [notes, setNotes] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [message, setMessage] = useState<{ text: string; ok: boolean } | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    setMessage(null);
    try {
      const body: Record<string, unknown> = {
        result,
        amount_recovered: result === "denied" ? 0 : parseFloat(amount) || 0,
        notes,
      };
      if (paidDate && result !== "denied") body.paid_date = paidDate;

      const res = await fetch(`/api/cases/${caseId}/outcome`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const data = await res.json();
      if (res.ok) {
        setMessage({ text: `Recorded: ${data.message}`, ok: true });
        onOutcomeRecorded();
      } else {
        setMessage({ text: data.detail || "Error recording outcome", ok: false });
      }
    } catch {
      setMessage({ text: "Network error", ok: false });
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="outcome-form">
      <h3>Record Outcome</h3>
      {message && (
        <div className={message.ok ? "msg-success" : "msg-error"}>{message.text}</div>
      )}
      <form onSubmit={handleSubmit}>
        <div className="form-row">
          <label>Result</label>
          <select value={result} onChange={(e) => setResult(e.target.value as typeof result)}>
            <option value="paid">Paid</option>
            <option value="partially_paid">Partially Paid</option>
            <option value="denied">Denied</option>
          </select>
        </div>
        {result !== "denied" && (
          <>
            <div className="form-row">
              <label>Amount Recovered ($)</label>
              <input
                type="number"
                min="0"
                step="0.01"
                value={amount}
                onChange={(e) => setAmount(e.target.value)}
                placeholder="0.00"
              />
            </div>
            <div className="form-row">
              <label>Paid Date</label>
              <input
                type="date"
                value={paidDate}
                onChange={(e) => setPaidDate(e.target.value)}
              />
            </div>
          </>
        )}
        <div className="form-row">
          <label>Notes</label>
          <textarea
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            rows={2}
            placeholder="Optional notes..."
          />
        </div>
        <button type="submit" disabled={submitting} className="btn-primary">
          {submitting ? "Saving..." : "Record Outcome"}
        </button>
      </form>
    </div>
  );
}
