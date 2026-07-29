import { useState } from "react";
import { Alert, Button, Dialog, DialogActions, DialogContent, DialogTitle, Stack, TextField } from "@mui/material";
import { Play } from "lucide-react";
import { postResource } from "./operationsApi";

interface Props {
  label: string;
  title: string;
  path: string;
  initialPayload: Record<string, unknown>;
  onCompleted?: () => void;
}

export function JsonActionDialog({ label, title, path, initialPayload, onCompleted }: Props) {
  const [open, setOpen] = useState(false);
  const [endpoint, setEndpoint] = useState(path);
  const [payloadText, setPayloadText] = useState(JSON.stringify(initialPayload, null, 2));
  const [error, setError] = useState("");
  const [result, setResult] = useState("");
  const [submitting, setSubmitting] = useState(false);

  async function submit(): Promise<void> {
    setError("");
    setResult("");
    let payload: unknown;
    try {
      payload = JSON.parse(payloadText) as unknown;
    } catch {
      setError("Payload must be valid JSON.");
      return;
    }
    setSubmitting(true);
    try {
      const response = await postResource(endpoint, payload);
      setResult(JSON.stringify(response, null, 2));
      onCompleted?.();
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Request failed.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <>
      <Button variant="contained" color="secondary" startIcon={<Play size={17} />} onClick={() => setOpen(true)}>{label}</Button>
      <Dialog open={open} onClose={() => setOpen(false)} fullWidth maxWidth="md">
        <DialogTitle>{title}</DialogTitle>
        <DialogContent dividers>
          <Stack spacing={2}>
            <TextField value={endpoint} onChange={(event) => setEndpoint(event.target.value)} label="API endpoint" fullWidth helperText="Relative to /api/v1. The field is editable to match the live OpenAPI contract." />
            <TextField multiline minRows={12} value={payloadText} onChange={(event) => setPayloadText(event.target.value)} label="JSON payload" fullWidth inputProps={{ style: { fontFamily: "monospace" } }} />
            {error && <Alert severity="error">{error}</Alert>}
            {result && <TextField multiline minRows={8} value={result} label="Response" fullWidth InputProps={{ readOnly: true }} inputProps={{ style: { fontFamily: "monospace" } }} />}
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setOpen(false)}>Close</Button>
          <Button variant="contained" disabled={submitting} onClick={() => void submit()}>{submitting ? "Submitting..." : "Submit"}</Button>
        </DialogActions>
      </Dialog>
    </>
  );
}
