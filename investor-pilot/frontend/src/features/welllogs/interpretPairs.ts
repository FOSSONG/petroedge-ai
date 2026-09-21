type Row=Record<string,number|null>;
const quantile=(sorted:number[],p:number)=>sorted[Math.floor((sorted.length-1)*p)];
const fmt=(n:number)=>Number(n.toPrecision(4)).toLocaleString();
export function interpretPairs(rows:Row[],x:string,y:string,logX=false,logY=false){
 if(!rows.length)return {highlight:[] as Row[],text:"No valid paired measurements in this interval.",meaning:"Map the required curves and units in LAS Wizard, or select another interval."};
 const xs=rows.map(r=>r[x]!),ys=rows.map(r=>r[y]!);
 const sx=[...xs].sort((a,b)=>a-b),sy=[...ys].sort((a,b)=>a-b);
 const cleanResistive=x==="gamma_ray_api"&&y==="resistivity_ohmm";
 const qx1=quantile(sx,.25),qx3=quantile(sx,.75),qy1=quantile(sy,.25),qy3=quantile(sy,.75);
 const candidates=rows.length<4?[]:rows.filter(r=>cleanResistive?(qx1<qx3&&qy1<qy3&&r[x]!<=qx1&&r[y]!>=qy3):(r[x]!<qx1-1.5*(qx3-qx1)||r[x]!>qx3+1.5*(qx3-qx1)||r[y]!<qy1-1.5*(qy3-qy1)||r[y]!>qy3+1.5*(qy3-qy1)));
 const stride=Math.max(1,Math.ceil(candidates.length/100)),highlight=candidates.filter((_,i)=>i%stride===0);
 const tx=xs.map(v=>logX?Math.log10(v):v),ty=ys.map(v=>logY?Math.log10(v):v);
 const mx=tx.reduce((a,b)=>a+b,0)/tx.length,my=ty.reduce((a,b)=>a+b,0)/ty.length;
 let cross=0,vx=0,vy=0;tx.forEach((v,i)=>{cross+=(v-mx)*(ty[i]-my);vx+=(v-mx)**2;vy+=(ty[i]-my)**2;});
 const r=vx&&vy?cross/Math.sqrt(vx*vy):null;
 const relation=rows.length<3||r===null?"There are too few varying pairs to estimate a relationship.":"Pearson r = "+r.toFixed(3)+(logX||logY?" in the displayed log coordinates.":".")+" The association is "+(Math.abs(r)<.3?"weak":Math.abs(r)<.7?"moderate":"strong")+" and "+(r<0?"inverse.":"positive.");
 const depths=candidates.map(row=>row.depth_m).filter((v):v is number=>typeof v==="number"&&Number.isFinite(v)).sort((a,b)=>a-b);
 const circleText=candidates.length?candidates.length+" samples meet the interest rule; "+highlight.length+" are circled"+(depths.length?" between "+fmt(depths[0])+" and "+fmt(depths[depths.length-1])+" m measured depth":"")+". These samples need not form a continuous interval.":"No samples meet the interest rule in this selection.";
 const meaning=cleanResistive?"Interest rule: GR at or below this interval's lower quartile and RT at or above its upper quartile. These are relatively low-gamma, resistive samples worth correlating with porosity and shale evidence; neither hydrocarbon phase nor pay is established.":
 x==="density_porosity"?"Circled points lie outside 1.5 interquartile ranges on either axis. Compare samples with the displayed Archie scenarios only when Rw, matrix density and clean-formation assumptions are appropriate; this is not a calibrated saturation result.":
 x==="caliper_in"?"Circled points lie outside 1.5 interquartile ranges on either axis. Compare caliper changes with the paired log for possible borehole influence; bit size and environmental corrections are needed to confirm washout.":
 "Circled points lie outside 1.5 interquartile ranges on either axis. Compare these unusual responses with adjacent depths and other logs to distinguish formation changes from measurement effects. Correlation alone does not identify lithology or fluids.";
 return {highlight,text:rows.length+" pairs: horizontal median "+fmt(quantile(sx,.5))+" (range "+fmt(sx[0])+"–"+fmt(sx[sx.length-1])+"); vertical median "+fmt(quantile(sy,.5))+" (range "+fmt(sy[0])+"–"+fmt(sy[sy.length-1])+"). "+relation+" "+circleText,meaning};
}
