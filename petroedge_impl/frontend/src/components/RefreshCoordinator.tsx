import { useEffect } from "react";
import { useQueryClient } from "@tanstack/react-query";

export function RefreshCoordinator(){
 const queryClient=useQueryClient();
 useEffect(()=>{
  let running=false;
  const refresh=async()=>{
   if(running)return;
   running=true;
   try{
    await queryClient.invalidateQueries();
    await queryClient.refetchQueries({type:"active"});
   } finally { running=false; }
  };
  const onCustom=()=>{void refresh();};
  const onClick=(event:MouseEvent)=>{
   const target=event.target instanceof Element?event.target.closest("button"):null;
   const label=target?.textContent?.trim().toLowerCase()??"";
   if(label==="refresh"||label.startsWith("refresh ")||label==="retry") setTimeout(()=>void refresh(),0);
  };
  window.addEventListener("petroedge:refresh",onCustom);
  document.addEventListener("click",onClick,true);
  return()=>{window.removeEventListener("petroedge:refresh",onCustom);document.removeEventListener("click",onClick,true);};
 },[queryClient]);
 return null;
}
