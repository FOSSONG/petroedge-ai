import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Alert, Button, Stack, TextField } from "@mui/material";
import { apiRequest } from "../../api/http";
export function RegisterMappedWell() {
 const [well, setWell] = useState(""); const [field, setField] = useState("");
 const cache = useQueryClient();
 const create = useMutation({mutationFn: () => apiRequest("/wells", {method:"POST", body:JSON.stringify({well_id:well.trim(),field:field.trim()})}), onSuccess: () => {void cache.invalidateQueries({queryKey:["wells"]});setWell("");}});
 return <Stack spacing={1}><Alert severity="info">Register a well here for mapped log analysis. Its ID must match the uploaded dataset's well name.</Alert><Stack direction={{xs:"column",md:"row"}} spacing={1}><TextField label="Mapped well ID" value={well} onChange={e=>setWell(e.target.value)}/><TextField label="Mapped well field" value={field} onChange={e=>setField(e.target.value)}/><Button disabled={!well.trim()||!field.trim()||create.isPending} onClick={()=>create.mutate()}>Register mapped well</Button></Stack>{create.isError&&<Alert severity="error">{create.error.message}</Alert>}{create.isSuccess&&<Alert severity="success">Well registered for mapped analysis.</Alert>}</Stack>;
}
