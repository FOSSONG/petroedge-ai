// @vitest-environment jsdom
import {render,screen,cleanup} from "@testing-library/react";
import {it,expect,vi,afterEach} from "vitest";
import {QueryClient,QueryClientProvider} from "@tanstack/react-query";
import {WellLogPlotlyPanel} from "./WellLogPlotlyPanel";
vi.mock("./platformApi",()=>({fetchDatasets:async()=>[{dataset_id:"d",name:"Partial logs"}]}));
vi.mock("../../api/http",()=>({apiRequest:async()=>({rows:[{depth_m:100,gamma_ray_api:40},{depth_m:101,gamma_ray_api:null},{depth_m:102,gamma_ray_api:50}],qc:"Pairwise QC"})}));
vi.mock("../../components/SafePlot",()=>({SafePlot:({data}:{data:unknown[]})=><pre data-testid="plot">{JSON.stringify(data)}</pre>}));
afterEach(cleanup);
it("plots available measured curves without complete interpretation inputs and preserves gaps",async()=>{
 render(<QueryClientProvider client={new QueryClient()}><WellLogPlotlyPanel/></QueryClientProvider>);
 const plot=await screen.findByTestId("plot");const traces=JSON.parse(plot.textContent!);
 expect(traces).toHaveLength(1);expect(traces[0].x).toEqual([40,null,50]);expect(traces[0].connectgaps).toBe(false);
});
