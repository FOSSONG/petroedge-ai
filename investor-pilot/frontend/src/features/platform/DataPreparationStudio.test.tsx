// @vitest-environment jsdom
import {cleanup,fireEvent,render,screen,waitFor} from "@testing-library/react";
import {afterEach,expect,it,vi} from "vitest";
import {QueryClient,QueryClientProvider} from "@tanstack/react-query";
import {DataPreparationStudio} from "./DataPreparationStudio";
import {fetchDatasetPreview,editDataset} from "./platformApi";
vi.mock("./platformApi",()=>({
 fetchDatasetPreview:vi.fn(async()=>({columns:Array.from({length:40},(_,i)=>`C${i}`),rows:Array.from({length:25},()=>Object.fromEntries(Array.from({length:40},(_,i)=>[`C${i}`,i]))),total_rows:2000})),
 fetchDatasetQuality:vi.fn(async()=>({unit_warnings:[],warnings:[]})),
 editDataset:vi.fn(),prepareDataset:vi.fn(),downloadDatasetFile:vi.fn()
}));
afterEach(()=>{cleanup();vi.clearAllMocks()});
it("bounds the rendered spreadsheet and mounts only the selected cell editor",async()=>{
 render(<QueryClientProvider client={new QueryClient({defaultOptions:{queries:{retry:false}}})}><DataPreparationStudio datasetId="d" datasets={[{dataset_id:"d",name:"Dataset",file_name:"data.csv"} as any]} onSelect={()=>{}}/></QueryClientProvider>);
 await screen.findByRole("button",{name:"Edit row 1 C0"},{timeout:10000});
 expect(fetchDatasetPreview).toHaveBeenCalledWith("d",0,25);
 expect(screen.getAllByRole("button",{name:/Edit row/})).toHaveLength(200);
 expect(screen.queryByRole("textbox",{name:/Edit row/})).toBeNull();
 fireEvent.click(screen.getByRole("button",{name:"Edit row 1 C0"}));
 expect(screen.getAllByRole("textbox",{name:/Edit row/})).toHaveLength(1);
 fireEvent.click(screen.getByRole("button",{name:"Next columns"}));
 expect(screen.queryByRole("button",{name:"Edit row 1 C0"})).toBeNull();
 expect(screen.getByRole("button",{name:"Edit row 1 C8"})).toBeTruthy();
},15000);

it("edits an appended row at the dataset end after a preceding deletion",async()=>{
 render(<QueryClientProvider client={new QueryClient({defaultOptions:{queries:{retry:false}}})}><DataPreparationStudio datasetId="d" datasets={[{dataset_id:"d",name:"Dataset"} as any]} onSelect={()=>{}}/></QueryClientProvider>);
 await screen.findByRole("button",{name:"Edit row 1 C0"},{timeout:10000});
 fireEvent.click(screen.getByRole("button",{name:"Add row"}));
 fireEvent.click(screen.getByRole("button",{name:"Delete row 1"}));
 fireEvent.click(screen.getByRole("button",{name:"Edit row 2000 C0"}));
 fireEvent.change(screen.getByRole("textbox",{name:"Edit row 2000 C0"}),{target:{value:"42"}});
 fireEvent.click(screen.getByRole("button",{name:"Save edited copy"}));
 await waitFor(()=>expect(editDataset).toHaveBeenCalledWith("d",expect.objectContaining({operations:[{action:"add_row",values:{}},{action:"delete_row",row:0},{action:"set_cell",row:1999,column:"C0",value:"42"}]})));
},15000);
