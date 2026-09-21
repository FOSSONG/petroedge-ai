// @vitest-environment jsdom
import {cleanup,fireEvent,render,screen,waitFor} from "@testing-library/react";
import {afterEach,expect,it,vi} from "vitest";
import {QueryClient,QueryClientProvider} from "@tanstack/react-query";
import {TrainingWorkspacePanel} from "./TrainingWorkspacePanel";
import * as api from "./platformApi";
vi.mock("./DataPreparationStudio",()=>({DataPreparationStudio:()=>null}));
vi.mock("./IndependentEvaluationPanel",()=>({IndependentEvaluationPanel:()=>null}));
vi.mock("./platformApi",()=>({
 fetchPredictionCompatibility:vi.fn(async()=>({ready:true,required_features:["GR"],complete_rows:100,total_rows:100,messages:[],policy:"Complete numeric inputs required"})),
 fetchDatasets:vi.fn(async()=>[{dataset_id:"d",name:"Well A",row_count:100}]),
 fetchPreparedTrainingDatasets:vi.fn(async()=>({datasets:[]})),
 fetchLifecycleAlgorithms:vi.fn(async()=>({algorithms:[{algorithm:"random_forest",display_name:"Random forest",available:true}]})),
 fetchLifecycleModels:vi.fn(async()=>({models:[{model_id:"m",display_name:"Test model",version:1,algorithm:"random_forest",task_type:"regression",validation_strategy:"grouped",created_at:"2026-01-01",metrics:{},dataset_id:"d",stage:"draft"}]})),
 fetchDatasetPreview:vi.fn(async()=>({columns:["GR","PHI"],rows:[]})),
 trainLifecycleModel:vi.fn(async()=>({})),predictWithLifecycleModel:vi.fn(async()=>({row_count:2,output_path:"predictions.csv",output_column:"prediction",preview:[]})),
 downloadPredictionFile:vi.fn(async()=>{throw new Error("Download unavailable")}),
 deleteLifecycleModel:vi.fn(),retrainLifecycleModel:vi.fn(),updateLifecycleStage:vi.fn()
}));
afterEach(()=>{cleanup();vi.clearAllMocks()});
function mount(){render(<QueryClientProvider client={new QueryClient({defaultOptions:{queries:{retry:false},mutations:{retry:false}}})}><TrainingWorkspacePanel/></QueryClientProvider>)}
it("keeps completed predictions on the results tab and displays download failures",async()=>{
 mount();fireEvent.click(screen.getByRole("tab",{name:"Predict dataset"}));
 await waitFor(()=>expect((screen.getByRole("button",{name:"Run prediction"}) as HTMLButtonElement).disabled).toBe(false));
 fireEvent.click(screen.getByRole("button",{name:"Run prediction"}));
 fireEvent.click(await screen.findByRole("button",{name:"Download complete CSV"}));
 expect(await screen.findByText("Download unavailable")).toBeTruthy();
 expect(screen.getByRole("tab",{name:"Predict dataset"}).getAttribute("aria-selected")).toBe("true");
});
it("refreshes training workspace data",async()=>{
 mount();await waitFor(()=>expect(api.fetchDatasets).toHaveBeenCalledTimes(1));
 fireEvent.click(screen.getByRole("button",{name:"Refresh training workspace"}));
 expect(await screen.findByText("Training workspace data refreshed.")).toBeTruthy();
 expect(api.fetchDatasets).toHaveBeenCalledTimes(2);
});
it("blocks target leakage and opens the registry after successful training",async()=>{
 mount();fireEvent.click(screen.getByRole("tab",{name:"Train model"}));
 await screen.findByRole("button",{name:"GR"});
 fireEvent.mouseDown(screen.getByLabelText("Target column"));
 fireEvent.click(await screen.findByRole("option",{name:"PHI"}));
 fireEvent.change(screen.getByLabelText("Feature columns"),{target:{value:"PHI"}});
 expect(screen.getByText("The target cannot also be a predictor.")).toBeTruthy();
 expect((screen.getByRole("button",{name:"Train and register model"}) as HTMLButtonElement).disabled).toBe(true);
 fireEvent.change(screen.getByLabelText("Feature columns"),{target:{value:"GR"}});
 fireEvent.click(screen.getByRole("button",{name:"Train and register model"}));
 await waitFor(()=>expect(screen.getByRole("tab",{name:"Model registry"}).getAttribute("aria-selected")).toBe("true"));
 expect(api.trainLifecycleModel).toHaveBeenCalledTimes(1);
});

it("blocks prediction when a required curve is absent",async()=>{
 vi.mocked(api.fetchPredictionCompatibility).mockResolvedValueOnce({ready:false,required_features:["GR","NPHI"],complete_rows:0,total_rows:100,messages:["Missing required columns: NPHI"],policy:"No automatic substitution",missing_columns:["NPHI"],empty_columns:[],invalid_counts:{NPHI:100}});
 mount();fireEvent.click(screen.getByRole("tab",{name:"Predict dataset"}));
 await screen.findByText(/Missing required columns: NPHI/);
 expect((screen.getByRole("button",{name:"Run prediction"}) as HTMLButtonElement).disabled).toBe(true);
 expect(api.predictWithLifecycleModel).not.toHaveBeenCalled();
});
