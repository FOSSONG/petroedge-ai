/** Display-only sampling. Full source rows remain in the result/download. */
export function researchPlotSamples<T>(rows:T[],limit=2000):T[]{
 if(!Number.isInteger(limit)||limit<2)throw new Error("Plot limit must be at least two.");
 if(rows.length<=limit)return rows;
 return Array.from({length:limit},(_,i)=>rows[Math.round(i*(rows.length-1)/(limit-1))]);
}
