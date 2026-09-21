// @vitest-environment jsdom
import {cleanup,render,screen} from "@testing-library/react";
import {afterEach,it,expect} from "vitest";
import {ModelReadinessPanel} from "./ModelReadinessPanel";
afterEach(cleanup);
it("shows failures and qualification limits without activation controls",()=>{render(<ModelReadinessPanel/>);expect(screen.getByText("Does not beat baseline")).toBeTruthy();expect(screen.getByText(/223 have zero/)).toBeTruthy();expect(screen.queryByRole("button",{name:/deploy|activate/i})).toBeNull()});
