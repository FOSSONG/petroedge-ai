// @vitest-environment jsdom
import {cleanup,fireEvent,render,screen,waitFor} from "@testing-library/react";
import {afterEach,it,expect,vi} from "vitest";
import {QueryClient,QueryClientProvider} from "@tanstack/react-query";
import {ResearchPredictionPanel} from "./ResearchPredictionPanel";
import {apiRequest} from "../../api/http";
vi.mock("../../components/SafePlot",()=>({SafePlot:()=> <div>Research plot</div>}));
vi.mock("./platformApi",()=>({fetchDatasets:vi.fn(async()=>[{dataset_id:"d",name:"Input logs",columns:["GR"]}])}));
vi.mock("../../api/http",()=>({apiRequest:vi.fn(async(path:string)=>path.endsWith("research-models")?{enabled:true,models:[{id:"m",name:"Demo porosity",features:[{name:"gr",unit:"API",min:1,max:3}],validation_rows:6,validation_mae:.03,unit:"fraction",limitations:["Experimental"]}]}:{model_name:"Demo porosity",unit:"fraction",condition:"190_bar",predicted_rows:1,rows:2,samples:[{source_row:0,prediction:.2,status:"predicted",reasons:[]},{source_row:1,prediction:null,status:"withheld",reasons:["outside training range"]}]})}));
afterEach(()=>{cleanup();vi.clearAllMocks()});
it("requires explicit mapping, units and acknowledgement; clears stale results when inputs change",async()=>{
 render(<QueryClientProvider client={new QueryClient({defaultOptions:{queries:{retry:false}}})}><ResearchPredictionPanel/></QueryClientProvider>);
 await waitFor(()=>expect(apiRequest).toHaveBeenCalled());
 fireEvent.mouseDown(screen.getByLabelText("Research model"));fireEvent.click(await screen.findByRole("option",{name:"Demo porosity"}));
 fireEvent.mouseDown(screen.getByLabelText("Input dataset"));fireEvent.click(await screen.findByRole("option",{name:"Input logs"}));
 expect((screen.getByRole("button",{name:"Run research prediction"}) as HTMLButtonElement).disabled).toBe(true);
 fireEvent.mouseDown(screen.getByLabelText("Source for gr"));fireEvent.click(await screen.findByRole("option",{name:"GR"}));
 fireEvent.change(screen.getByLabelText("Source unit for gr"),{target:{value:"API"}});
 fireEvent.click(screen.getByRole("checkbox"));fireEvent.click(screen.getByRole("button",{name:"Run research prediction"}));
 expect(await screen.findByText("outside training range")).toBeTruthy();
 expect(screen.getByRole("button",{name:"Download research results Excel"})).toBeTruthy();
 fireEvent.change(screen.getByLabelText("Source unit for gr"),{target:{value:"GAPI"}});
 expect(screen.queryByText("Research plot")).toBeNull();expect((screen.getByRole("checkbox") as HTMLInputElement).checked).toBe(false);
});
