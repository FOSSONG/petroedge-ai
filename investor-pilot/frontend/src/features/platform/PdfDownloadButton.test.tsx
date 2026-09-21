// @vitest-environment jsdom
import {cleanup,fireEvent,render,screen} from "@testing-library/react";
import {afterEach,expect,it,vi} from "vitest";
import {PdfDownloadButton} from "./PdfDownloadButton";
import {downloadV1Report} from "./platformApi";
vi.mock("./platformApi",()=>({downloadV1Report:vi.fn()}));
afterEach(()=>{cleanup();vi.resetAllMocks();});
it("shows an accessible PDF fallback after generation",async()=>{
 vi.mocked(downloadV1Report).mockResolvedValue({url:"blob:test",fileName:"logs.pdf"});
 render(<PdfDownloadButton datasetId="test"/>);
 fireEvent.click(screen.getByRole("button",{name:"Download PDF"}));
 const link=await screen.findByRole("link",{name:"open PDF"});
 expect(link.getAttribute("href")).toBe("blob:test");
 expect(downloadV1Report).toHaveBeenCalledWith("test");
});
it("shows the actionable server failure rather than failing silently",async()=>{
 vi.mocked(downloadV1Report).mockRejectedValue(new Error("Choose GR or GR_COMP in LAS Wizard"));
 render(<PdfDownloadButton datasetId="test"/>);
 fireEvent.click(screen.getByRole("button",{name:"Download PDF"}));
 expect((await screen.findByRole("alert")).textContent).toContain("Choose GR or GR_COMP");
});
