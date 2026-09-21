// @vitest-environment jsdom
import {cleanup,fireEvent,render,screen,waitFor} from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import {QueryClient,QueryClientProvider} from "@tanstack/react-query";
import {afterEach,beforeEach,expect,it,vi} from "vitest";
import {IndependentEvaluationPanel} from "./IndependentEvaluationPanel";
import {fetchIndependentEvaluation,runIndependentEvaluation} from "./platformApi";
vi.mock("./platformApi",()=>({fetchIndependentEvaluation:vi.fn(),runIndependentEvaluation:vi.fn()}));
const policy={policy_id:"fixture",minimum_test_rows:5,minimum_test_groups:1,criteria:{mae:{max:1}}};
let client:QueryClient;
beforeEach(()=>{vi.resetAllMocks();localStorage.setItem("petroedge_roles",JSON.stringify(["admin"]));client=new QueryClient({defaultOptions:{queries:{retry:false}}});});
afterEach(()=>{cleanup();client.clear();localStorage.clear();});
function show(){render(<QueryClientProvider client={client}><IndependentEvaluationPanel modelId="fixture"/></QueryClientProvider>);}
it("requires confirmation before consuming test data",async()=>{
  vi.mocked(fetchIndependentEvaluation).mockResolvedValue({status:"not_evaluated",policy});
  vi.mocked(runIndependentEvaluation).mockResolvedValue({model_id:"fixture",passed:true,metrics:{mae:.2},failures:[],test_rows:10,test_groups:1,evaluated_at:"now",actor:"admin"});
  show();fireEvent.click(await screen.findByRole("button",{name:"Review and run independent test"}));
  expect(await screen.findByRole("dialog")).toBeInTheDocument();expect(runIndependentEvaluation).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole("button",{name:"Run final test"}));
  await waitFor(()=>expect(runIndependentEvaluation).toHaveBeenCalledExactlyOnceWith("fixture"));
});
it("does not offer evaluation without an approved policy",async()=>{
  vi.mocked(fetchIndependentEvaluation).mockResolvedValue({status:"not_evaluated"});show();
  expect(await screen.findByText(/No evaluation policy/)).toBeInTheDocument();
  expect(screen.queryByRole("button",{name:"Review and run independent test"})).not.toBeInTheDocument();
});
it("does not request test results for a nonadministrator",()=>{
  localStorage.setItem("petroedge_roles",JSON.stringify(["engineer"]));show();
  expect(screen.getByText(/requires an administrator/)).toBeInTheDocument();expect(fetchIndependentEvaluation).not.toHaveBeenCalled();
});
