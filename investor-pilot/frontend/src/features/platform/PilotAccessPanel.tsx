import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Alert, Button, Paper, Stack, TextField, Typography } from "@mui/material";
import { apiRequest } from "../../api/http";

type Customer = {id:string;email:string;role:string;is_active:boolean};
export function PilotAccessPanel() {
 const client=useQueryClient();
 const state=useQuery({queryKey:["pilot-access"],queryFn:()=>apiRequest<{paused:boolean}>("/pilot/access"),retry:false});
 const users=useQuery({queryKey:["pilot-customers"],queryFn:()=>apiRequest<Customer[]>("/pilot/customers"),retry:false,enabled:state.isSuccess});
 const [email,setEmail]=useState("");const [name,setName]=useState("");const [password,setPassword]=useState("");
 const change=useMutation({mutationFn:(paused:boolean)=>apiRequest("/pilot/access",{method:"PUT",body:JSON.stringify({paused})}),onSuccess:()=>client.invalidateQueries({queryKey:["pilot-access"]})});
 const active=useMutation({mutationFn:(u:Customer)=>apiRequest(`/pilot/customers/${u.id}/active`,{method:"PUT",body:JSON.stringify({is_active:!u.is_active})}),onSuccess:()=>client.invalidateQueries({queryKey:["pilot-customers"]})});
 const create=useMutation({mutationFn:()=>apiRequest("/pilot/customers",{method:"POST",body:JSON.stringify({email,full_name:name,password,role:"viewer"})}),onSuccess:()=>{setPassword("");setEmail("");setName("");void client.invalidateQueries({queryKey:["pilot-customers"]});}});
 return <Paper variant="outlined" sx={{p:3}}><Stack spacing={2}>
  <Typography variant="h6">Pilot owner controls</Typography>
  {state.isError ? <Alert severity="info">Owner controls require a configured pilot owner and that owner's administrator login.</Alert> : state.data && <>
   <Alert severity={state.data.paused?"warning":"success"}>{state.data.paused?"Customer access is paused. Your owner access remains available.":"Customer access is enabled."}</Alert>
   <Button color={state.data.paused?"success":"warning"} variant="contained" disabled={change.isPending} onClick={()=>change.mutate(!state.data!.paused)}>{state.data.paused?"Resume customer access":"Pause all customer access"}</Button>
   <Typography>Disabling an account blocks its existing access token on the next request. Global live event feeds are owner-only during the pilot. Data already downloaded cannot be recalled.</Typography>
   <Button onClick={()=>{void state.refetch();void users.refetch();}}>Refresh access status</Button>
   {(users.data??[]).map(u=><Stack key={u.id} direction="row" gap={2} alignItems="center"><Typography>{u.email} | {u.role} | {u.is_active?"enabled":"disabled"}</Typography>{u.role!=="admin"&&u.role!=="administrator"&&<Button disabled={active.isPending} onClick={()=>active.mutate(u)}>{u.is_active?"Disable account":"Enable account"}</Button>}</Stack>)}
   <Typography variant="subtitle1">Create an invited viewer</Typography>
   <TextField label="Customer email" value={email} onChange={e=>setEmail(e.target.value)}/><TextField label="Customer name" value={name} onChange={e=>setName(e.target.value)}/><TextField label="Initial password (12+ characters)" type="password" autoComplete="new-password" value={password} onChange={e=>setPassword(e.target.value)}/>
   <Button disabled={create.isPending||!email||name.length<2||password.length<12} onClick={()=>create.mutate()}>Create viewer account</Button>
  </>}
  {[change,active,create].map((m,i)=>m.isError&&<Alert key={i} severity="error">{m.error.message}</Alert>)}
  {create.isSuccess&&<Alert severity="success">Viewer account created. Share credentials privately.</Alert>}
 </Stack></Paper>;
}
