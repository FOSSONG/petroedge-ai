import { useState } from "react";
import { Alert, Button, Link, Stack } from "@mui/material";
import { downloadV1Report } from "./platformApi";
export function PdfDownloadButton({datasetId,disabled=false}:{datasetId:string;disabled?:boolean}) {
 const [busy,setBusy]=useState(false);const [error,setError]=useState("");const [file,setFile]=useState<{url:string;fileName:string}|null>(null);
 return <Stack spacing={1}><Button variant="contained" disabled={disabled||!datasetId||busy} onClick={async()=>{setBusy(true);setError("");setFile(null);try{setFile(await downloadV1Report(datasetId));}catch(e){setError(e instanceof Error?e.message:"PDF export failed");}finally{setBusy(false);}}}>{busy?"Generating PDF...":"Download PDF"}</Button>{error&&<Alert severity="error">{error}</Alert>}{file&&<Alert severity="success">PDF generated. If no download appeared, <Link href={file.url} target="_blank" rel="noopener">open PDF</Link> or <Link href={file.url} download={file.fileName}>save PDF</Link> (available for 5 minutes).</Alert>}</Stack>;
}
