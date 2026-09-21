import {useState} from "react";
import {useMutation,useQuery,useQueryClient} from "@tanstack/react-query";
import {Alert,Button,Dialog,DialogActions,DialogContent,DialogTitle,Stack,Typography} from "@mui/material";
import {restoreSession} from "../../auth/session";
import {fetchIndependentEvaluation,runIndependentEvaluation} from "./platformApi";

export function IndependentEvaluationPanel({modelId}:{modelId:string}) {
  const admin=restoreSession().roles.some(r=>["admin","administrator"].includes(r.toLowerCase()));
  const [confirm,setConfirm]=useState(false);
  const qc=useQueryClient();
  const status=useQuery({queryKey:["independent-evaluation",modelId],queryFn:()=>fetchIndependentEvaluation(modelId),enabled:admin});
  const evaluate=useMutation({mutationFn:()=>runIndependentEvaluation(modelId),onSettled:async()=>{setConfirm(false);await qc.invalidateQueries({queryKey:["independent-evaluation",modelId]});}});
  if(!admin)return <Typography variant="body2">Independent test evaluation requires an administrator.</Typography>;
  const result=status.data?.status==="completed"?status.data.result:undefined;
  return <Stack spacing={1} mt={2}>
    <Typography fontWeight={600}>Independent test evaluation</Typography>
    {status.isLoading&&<Typography>Loading evaluation status?</Typography>}
    {(status.isError||evaluate.isError)&&<Alert severity="error">{String((evaluate.error||status.error) instanceof Error?(evaluate.error||status.error)?.message:"Evaluation unavailable")}</Alert>}
    {result&&<Alert severity={result.passed?"success":"warning"}>{result.passed?"Predeclared criteria passed":"Predeclared criteria failed"}. {result.test_rows} test rows in {result.test_groups} groups. {result.failures.join("; ")}</Alert>}
    {result&&Object.entries(result.metrics).map(([metric,value])=><Typography key={metric} variant="body2">{metric}: {value.toFixed(4)}</Typography>)}
    {status.data?.status==="not_evaluated"&&!status.data.policy&&<Alert severity="info">No evaluation policy was approved before training. This model cannot consume the reserved test set.</Alert>}
    {status.data?.status==="not_evaluated"&&status.data.policy&&<Button onClick={()=>setConfirm(true)}>Review and run independent test</Button>}
    {["running","failed"].includes(status.data?.status??"")&&<Alert severity="warning">Evaluation {status.data?.status}. Test reservations are retained; automatic retries are blocked.</Alert>}
    <Typography variant="caption">Passing permits validation status. Production deployment still requires operational approval.</Typography>
    <Dialog open={confirm} onClose={()=>!evaluate.isPending&&setConfirm(false)}>
      <DialogTitle>Use the reserved independent test set?</DialogTitle>
      <DialogContent><Typography>This records the final test result for this candidate. These test specimens cannot be used to compare another candidate.</Typography>
        <Typography mt={2}>Policy: {status.data?.policy?.policy_id}</Typography>
        {Object.entries(status.data?.policy?.criteria??{}).map(([metric,bounds])=><Typography key={metric}>{metric}: {bounds.min!==undefined?`minimum ${bounds.min}`:""} {bounds.max!==undefined?`maximum ${bounds.max}`:""}</Typography>)}
      </DialogContent>
      <DialogActions><Button disabled={evaluate.isPending} onClick={()=>setConfirm(false)}>Cancel</Button><Button disabled={evaluate.isPending} onClick={()=>evaluate.mutate()}>Run final test</Button></DialogActions>
    </Dialog>
  </Stack>;
}
