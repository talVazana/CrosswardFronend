import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, fireEvent, cleanup, waitFor } from "@testing-library/react";

const { mockPush, mockAuthCallback } = vi.hoisted(() => ({
  mockPush: vi.fn(),
  mockAuthCallback: { current: undefined as undefined | ((user: unknown) => void) },
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: mockPush,
    replace: vi.fn(),
    refresh: vi.fn(),
    back: vi.fn(),
    forward: vi.fn(),
    prefetch: vi.fn(),
  }),
  useParams: () => ({ roomId: "room-42" }),
}));

const { mockRoomFetch, mockSetRoomSessionToken } = vi.hoisted(() => ({
  mockRoomFetch: vi.fn(),
  mockSetRoomSessionToken: vi.fn(),
}));

vi.mock("@/lib/roomSession", () => ({
  roomFetch: mockRoomFetch,
  setRoomSessionToken: mockSetRoomSessionToken,
}));

const { mockGetProfile, mockSaveProfile, mockSignInWithGoogle, mockGetIdToken } = vi.hoisted(
  () => ({
    mockGetProfile: vi.fn(),
    mockSaveProfile: vi.fn(),
    mockSignInWithGoogle: vi.fn(),
    mockGetIdToken: vi.fn(),
  }),
);

vi.mock("@/lib/auth", () => ({
  onAuthChange: (cb: (user: unknown) => void) => {
    mockAuthCallback.current = cb;
    return () => {};
  },
  getProfile: mockGetProfile,
  saveProfile: mockSaveProfile,
  signInWithGoogle: mockSignInWithGoogle,
  getIdToken: mockGetIdToken,
}));

import Page from "../src/app/rooms/[roomId]/join/page";

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
  mockPush.mockReset();
  mockAuthCallback.current = undefined;
});

describe("TASK-012 join page (Google-only)", () => {
  it("shows the Google sign-in button when no one is signed in", () => {
    render(<Page />);

    expect(screen.getByRole("button", { name: "Sign in with Google" })).toBeTruthy();
    expect(screen.queryByRole("textbox")).toBeNull();
  });

  it("shows a nickname form when signed in without a nickname", async () => {
    mockGetProfile.mockResolvedValue({ email: "a@b.com", nickname: null });
    render(<Page />);
    mockAuthCallback.current?.({ uid: "u1" });

    expect(await screen.findByRole("textbox")).toBeTruthy();
    expect(screen.getByRole("button", { name: /save nickname/i })).toBeTruthy();
  });

  it("saving a nickname calls saveProfile", async () => {
    mockGetProfile.mockResolvedValue({ email: "a@b.com", nickname: null });
    mockSaveProfile.mockResolvedValue({ email: "a@b.com", nickname: "Dana" });
    render(<Page />);
    mockAuthCallback.current?.({ uid: "u1" });

    const input = await screen.findByRole("textbox");
    fireEvent.change(input, { target: { value: "Dana" } });
    fireEvent.click(screen.getByRole("button", { name: /save nickname/i }));

    await waitFor(() => expect(mockSaveProfile).toHaveBeenCalledWith("Dana"));
  });

  it("shows a Join button using the nickname when signed in", async () => {
    mockGetProfile.mockResolvedValue({ email: "a@b.com", nickname: "Dana" });
    render(<Page />);
    mockAuthCallback.current?.({ uid: "u1" });

    expect(await screen.findByRole("button", { name: "Join as Dana" })).toBeTruthy();
  });

  it("joins via roomFetch and navigates on success", async () => {
    mockGetProfile.mockResolvedValue({ email: "a@b.com", nickname: "Dana" });
    mockGetIdToken.mockResolvedValue("fake-token");
    mockRoomFetch.mockResolvedValue({
      ok: true,
      json: async () => ({ sessionToken: "tok" }),
    });
    render(<Page />);
    mockAuthCallback.current?.({ uid: "u1" });

    fireEvent.click(await screen.findByRole("button", { name: "Join as Dana" }));

    await waitFor(() => expect(mockRoomFetch).toHaveBeenCalledTimes(1));
    const [roomId, path, init] = mockRoomFetch.mock.calls[0];
    expect(roomId).toBe("room-42");
    expect(String(path)).toContain("/rooms/room-42/join");
    expect((init as RequestInit).method).toBe("POST");
    expect(mockPush).toHaveBeenCalledWith("/rooms/room-42");
  });

  it("shows an error message when joining fails", async () => {
    mockGetProfile.mockResolvedValue({ email: "a@b.com", nickname: "Dana" });
    mockGetIdToken.mockResolvedValue("fake-token");
    mockRoomFetch.mockResolvedValue({
      ok: false,
      status: 404,
      json: async () => ({ detail: "Room not found" }),
    });
    render(<Page />);
    mockAuthCallback.current?.({ uid: "u1" });

    fireEvent.click(await screen.findByRole("button", { name: "Join as Dana" }));

    const alert = await screen.findByRole("alert");
    expect(alert.textContent ?? "").toMatch(/not found/i);
    expect(mockPush).not.toHaveBeenCalled();
  });

  it("shows no color picker because colors are assigned by the system", () => {
    const { container } = render(<Page />);

    expect(container.querySelector('input[type="color"]')).toBeNull();
    expect(screen.queryByText(/color/i)).toBeNull();
  });
});
