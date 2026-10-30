import { api, ApiError, apiMode, getToken, setToken } from "./api";
export type AuthProvider = "password" | "google";
export type AccountType = "seeker" | "owner";
export interface Premium {
  planId: string;
  until: string;
}
export interface User {
  id: string;
  firstName: string;
  lastName: string;
  username: string;
  email: string;
  phone: string;
  country: string;
  provider: AuthProvider;
  accountType: AccountType;
  idVerified: boolean;
  isAdmin?: boolean;
  premium: Premium | null;
  createdAt: string;
}
export interface SignUpInput {
  firstName: string;
  lastName: string;
  username: string;
  email: string;
  phone: string;
  country: string;
  password: string;
  accountType: AccountType;
  emailCode?: string;
}
export type ProfileInput = Omit<SignUpInput, "password" | "accountType" | "emailCode">;
export class AuthError extends Error {
  constructor(message: string, public field?: string) {
    super(message);
  }
}
export interface AuthService {
  current(): Promise<User | null>;
  requestSignUpCode(input: SignUpInput): Promise<{ demoCode?: string }>;
  signUp(input: SignUpInput): Promise<User>;
  signIn(identifier: string, password: string): Promise<User>;
  signInWithGoogle(email: string): Promise<User>;
  requestPasswordReset(email: string): Promise<void>;
  updateProfile(input: ProfileInput): Promise<User>;
  setAccountType(type: AccountType): Promise<User>;
  verifyIdentity(docType: string, file?: File): Promise<User>;
  activatePremium(planId: string, days: number): Promise<User>;
  signOut(): Promise<void>;
}
export function isPremium(u: User | null, now = Date.now()): boolean {
  return !!u?.premium && new Date(u.premium.until).getTime() > now;
}
export const COUNTRIES = [
  { name: "India", dial: "+91" },
  { name: "United States", dial: "+1" },
  { name: "United Kingdom", dial: "+44" },
  { name: "Canada", dial: "+1" },
  { name: "Australia", dial: "+61" },
  { name: "United Arab Emirates", dial: "+971" },
  { name: "Singapore", dial: "+65" },
  { name: "Germany", dial: "+49" },
  { name: "Nepal", dial: "+977" },
  { name: "Bangladesh", dial: "+880" },
  { name: "Sri Lanka", dial: "+94" },
];
export function isProfileComplete(u: User): boolean {
  return Boolean(u.firstName && u.lastName && u.username && u.email && u.phone && u.country);
}
export function validateProfile(p: ProfileInput): Record<string, string> {
  const e: Record<string, string> = {};
  if (!p.firstName.trim()) e.firstName = "Enter your first name.";
  if (!p.lastName.trim()) e.lastName = "Enter your surname.";
  if (!/^[a-z0-9_]{3,20}$/.test(p.username)) e.username = "Use 3 to 20 lowercase letters, numbers or underscores.";
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(p.email)) e.email = "Enter a valid email address.";
  const digits = p.phone.replace(/\D/g, "");
  if (p.phone.startsWith("+91") ? digits.length !== 12 : digits.length < 8) e.phone = "Enter a valid phone number.";
  if (!p.country) e.country = "Choose your country.";
  return e;
}
export function validatePassword(pw: string): string | null {
  if (pw.length < 8) return "Use at least 8 characters.";
  if (!/[A-Za-z]/.test(pw) || !/\d/.test(pw)) return "Include at least one letter and one number.";
  return null;
}
const USERS_KEY = "trustrent-users";
const SESSION_KEY = "trustrent-session";
export const DEMO_OTP = "123456";
interface StoredUser {
  user: User;
  passwordHash?: string;
}
async function sha256(text: string): Promise<string> {
  const buf = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(text));
  return Array.from(new Uint8Array(buf)).map((b) => b.toString(16).padStart(2, "0")).join("");
}
function normPhone(p: string) {
  return "+" + p.replace(/\D/g, "");
}
class LocalAuthService implements AuthService {
  private load(): StoredUser[] {
    try {
      return JSON.parse(localStorage.getItem(USERS_KEY) || "[]");
    } catch {
      return [];
    }
  }
  private save(list: StoredUser[]) {
    localStorage.setItem(USERS_KEY, JSON.stringify(list));
  }
  private startSession(u: User) {
    localStorage.setItem(SESSION_KEY, u.id);
    return u;
  }
  private newUser(partial: Partial<User> & { provider: AuthProvider }): User {
    return {
      id: crypto.randomUUID(),
      firstName: "", lastName: "", username: "", email: "", phone: "", country: "",
      accountType: "seeker", idVerified: false, premium: null,
      createdAt: new Date().toISOString(),
      ...partial,
    };
  }
  async current() {
    const id = localStorage.getItem(SESSION_KEY);
    const u = this.load().find((s) => s.user.id === id)?.user;
    return u ? this.upgrade(u) : null;
  }
  async requestSignUpCode(input: SignUpInput) {
    this.checkNewAccount(input);
    return { demoCode: DEMO_OTP };
  }
  private checkNewAccount(input: SignUpInput) {
    const errors = validateProfile(input);
    const first = Object.entries(errors)[0];
    if (first) throw new AuthError(first[1], first[0]);
    const pwError = validatePassword(input.password);
    if (pwError) throw new AuthError(pwError, "password");
    const list = this.load();
    if (list.some((s) => s.user.username === input.username)) throw new AuthError("That username is taken.", "username");
    if (list.some((s) => s.user.email.toLowerCase() === input.email.toLowerCase()))
      throw new AuthError("An account with this email already exists. Sign in instead.", "email");
    return list;
  }
  async signUp(input: SignUpInput) {
    const list = this.checkNewAccount(input);
    if (input.emailCode !== DEMO_OTP) throw new AuthError("That code isn't right. Check the email and try again.", "emailCode");
    const { password, emailCode, ...profile } = input;
    void emailCode;
    const user = this.newUser({ ...profile, phone: normPhone(profile.phone), provider: "password" });
    list.push({ user, passwordHash: await sha256(password) });
    this.save(list);
    return this.startSession(user);
  }
  async signIn(identifier: string, password: string) {
    const id = identifier.trim().toLowerCase();
    const hash = await sha256(password);
    const found = this.load().find((s) => s.user.username === id || s.user.email.toLowerCase() === id);
    if (!found || found.passwordHash !== hash) throw new AuthError("Wrong username or password.");
    return this.startSession(this.upgrade(found.user));
  }
  private upgrade(u: User): User {
    return { ...u, accountType: u.accountType ?? "seeker", idVerified: u.idVerified ?? false, premium: u.premium ?? null };
  }
  private async patchMe(patch: Partial<User>): Promise<User> {
    const me = await this.current();
    if (!me) throw new AuthError("Your session ended. Sign in again.");
    const updated = { ...me, ...patch };
    this.save(this.load().map((s) => (s.user.id === me.id ? { ...s, user: updated } : s)));
    return updated;
  }
  async setAccountType(type: AccountType) {
    return this.patchMe({ accountType: type });
  }
  async verifyIdentity(docType: string) {
    if (!docType) throw new AuthError("Choose an ID document.");
    return this.patchMe({ idVerified: true });
  }
  async activatePremium(planId: string, days: number) {
    const me = await this.current();
    if (!me) throw new AuthError("Your session ended. Sign in again.");
    if (!me.idVerified) throw new AuthError("Verify your identity before upgrading.");
    const start = isPremium(me) ? new Date(me.premium!.until).getTime() : Date.now();
    return this.patchMe({ premium: { planId, until: new Date(start + days * 86_400_000).toISOString() } });
  }
  async signInWithGoogle(email: string) {
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(email)) throw new AuthError("Enter a valid Google email.", "email");
    const list = this.load();
    let found = list.find((s) => s.user.email.toLowerCase() === email.toLowerCase());
    if (!found) {
      found = { user: this.newUser({ email: email.toLowerCase(), provider: "google" }) };
      list.push(found);
      this.save(list);
    }
    return this.startSession(this.upgrade(found.user));
  }
  async requestPasswordReset(email: string) {
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(email)) throw new AuthError("Enter a valid email address.", "email");
  }
  async updateProfile(input: ProfileInput) {
    const errors = validateProfile(input);
    const first = Object.entries(errors)[0];
    if (first) throw new AuthError(first[1], first[0]);
    const me = await this.current();
    if (!me) throw new AuthError("Your session ended. Sign in again.");
    const list = this.load();
    if (list.some((s) => s.user.id !== me.id && s.user.username === input.username))
      throw new AuthError("That username is taken.", "username");
    if (list.some((s) => s.user.id !== me.id && s.user.email.toLowerCase() === input.email.toLowerCase()))
      throw new AuthError("Another account already uses this email.", "email");
    const updated: User = { ...me, ...input, phone: normPhone(input.phone) };
    this.save(list.map((s) => (s.user.id === me.id ? { ...s, user: updated } : s)));
    return updated;
  }
  async signOut() {
    localStorage.removeItem(SESSION_KEY);
  }
}
class ApiAuthService implements AuthService {
  private async session(p: Promise<{ access_token: string; user: User }>): Promise<User> {
    const { access_token, user } = await p;
    setToken(access_token);
    return user;
  }
  private async call<T>(fn: () => Promise<T>): Promise<T> {
    try {
      return await fn();
    } catch (e) {
      if (e instanceof ApiError) throw new AuthError(e.message, e.field);
      throw e;
    }
  }
  async current() {
    if (!getToken()) return null;
    try {
      return (await api<{ user: User }>("/users/me")).user;
    } catch (e) {
      if (e instanceof ApiError && (e.status === 401 || e.status === 403 || e.status === 404)) setToken(null);
      return null;
    }
  }
  requestSignUpCode(input: SignUpInput) {
    return this.call(async () => {
      const r = await api<{ demoCode?: string | null }>("/auth/signup/email-code", { json: input });
      return { demoCode: r.demoCode ?? undefined };
    });
  }
  signUp(input: SignUpInput) {
    return this.call(() => this.session(api("/auth/signup", { json: input })));
  }
  signIn(identifier: string, password: string) {
    return this.call(() => this.session(api("/auth/password-login", { json: { identifier, password } })));
  }
  signInWithGoogle(emailOrCredential: string) {
    const body = emailOrCredential.includes("@") ? { email: emailOrCredential } : { credential: emailOrCredential };
    return this.call(() => this.session(api("/auth/google", { json: body })));
  }
  async requestPasswordReset(email: string) {
    await this.call(() => api("/auth/password/forgot", { json: { email } }));
  }
  async updateProfile(input: ProfileInput) {
    return this.call(async () => (await api<{ user: User }>("/users/me", { method: "PUT", json: input })).user);
  }
  async setAccountType(accountType: AccountType) {
    return this.call(async () => (await api<{ user: User }>("/users/me/account-type", { method: "PUT", json: { accountType } })).user);
  }
  async verifyIdentity(docType: string, file?: File) {
    if (!file) throw new AuthError("Upload a photo or scan of the document.", "file");
    const form = new FormData();
    form.append("docType", docType);
    form.append("file", file);
    return this.call(async () => (await api<{ user: User }>("/users/me/identity", { form })).user);
  }
  async activatePremium(planId: string) {
    return this.call(async () => (await api<{ user: User }>("/subscriptions", { json: { planId } })).user);
  }
  async signOut() {
    setToken(null);
  }
}
export const authMode: "demo" | "api" = apiMode ? "api" : "demo";
export const authService: AuthService = apiMode ? new ApiAuthService() : new LocalAuthService();
