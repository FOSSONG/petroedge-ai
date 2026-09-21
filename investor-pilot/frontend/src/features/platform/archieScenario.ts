export type ArchieInputs={phi:number;rt:number;rw:number;a:number;m:number;n:number};
export function archieScenario(p:ArchieInputs){
 if(!Object.values(p).every(Number.isFinite))throw new Error("Enter finite values for every parameter.");
 if(p.phi<=0||p.phi>1)throw new Error("Porosity must be a fraction greater than 0 and at most 1.");
 if(p.rt<=0||p.rw<=0||p.a<=0||p.m<=0||p.n<=0)throw new Error("Resistivity and Archie coefficients must be greater than zero.");
 const raw=Math.exp((Math.log(p.a)+Math.log(p.rw)-Math.log(p.rt)-p.m*Math.log(p.phi))/p.n);
 if(!Number.isFinite(raw)||raw===0)throw new Error("Parameters exceed the supported numerical range.");
 return {raw,bounded:Math.min(1,raw),aboveOne:raw>1};
}
