// @vitest-environment jsdom
import {cleanup,render,screen,waitFor} from "@testing-library/react";
import {afterEach,expect,it,vi} from "vitest";
import {SafePlot} from "./SafePlot";
const engine=vi.hoisted(()=>({react:vi.fn().mockResolvedValue(undefined),purge:vi.fn()}));
vi.mock("plotly.js-dist-min",()=>({default:engine}));
afterEach(()=>{cleanup();vi.clearAllMocks();});
it("does not redraw indefinitely when config is omitted",async()=>{
 render(<SafePlot data={[]} layout={{}}/>);
 await waitFor(()=>expect(screen.queryByText(/Loading interactive chart/)).toBeNull());
 expect(engine.react).toHaveBeenCalledTimes(1);
});
