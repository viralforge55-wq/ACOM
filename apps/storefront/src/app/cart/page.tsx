"use client";

import { FormEvent, useEffect, useState } from "react";
import { formatMoney } from "@/lib/format";
import type { Money } from "@/types/catalog";

type Cart = { lines: { product_slug: string; title: string; quantity: number; line_total: Money }[]; total: Money; cart_token: string };
type Order = { checkout_id: string; status: string; total?: Money; amount?: Money };

export default function CartPage() {
  const [cart, setCart] = useState<Cart>();
  const [order, setOrder] = useState<Order>();
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [key, setKey] = useState("");
  async function validate() {
    const items = JSON.parse(localStorage.getItem("acom-cart") || "[]");
    if (!items.length) { setMessage("Your cart is empty."); setCart(undefined); return; }
    const response = await fetch("/api/cart/validate", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ items }) });
    const result = await response.json();
    if (result.ok) { setCart(result.data); setKey(crypto.randomUUID()); setMessage(""); }
    else setMessage(result.error.message);
  }
  useEffect(() => { void validate().catch(() => setMessage("Could not load cart.")); }, []);
  async function signIn(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true);
    const data = new FormData(event.currentTarget);
    try {
      const response = await fetch("/api/auth/login", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ usr: data.get("email"), pwd: data.get("password") }) });
      setMessage(response.ok ? "Signed in. You can now check out." : "Sign-in failed.");
    } finally { setBusy(false); }
  }
  async function checkout(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); if (!cart) return; setBusy(true);
    const data = new FormData(event.currentTarget);
    try {
      const response = await fetch("/api/checkout", { method: "POST", headers: { "Content-Type": "application/json", "Idempotency-Key": key }, body: JSON.stringify({ cart_token: cart.cart_token, payment_method: "gateway",
        customer: { name: data.get("name"), email: data.get("email"), phone: data.get("phone") },
        shipping_address: { line1: data.get("line1"), city: data.get("city"), state: data.get("state"), pincode: data.get("pincode"), country: "IN" } }) });
      const result = await response.json();
      if (result.ok) { setOrder(result.data); setMessage("Checkout created. Payment awaits a verified test-gateway webhook."); }
      else setMessage(result.error.message);
    } catch { setMessage("Checkout unavailable. Retry safely with the same request."); }
    finally { setBusy(false); }
  }
  async function refreshOrder() {
    if (!order) return;
    const response = await fetch(`/api/orders/${encodeURIComponent(order.checkout_id)}`, { cache: "no-store" });
    const result = await response.json();
    if (result.ok) setOrder(result.data); else setMessage(result.error.message);
  }
  async function simulatePayment() {
    if (!order) return;
    setBusy(true);
    try {
      const response = await fetch("/api/checkout/test-payment", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ checkout_id: order.checkout_id }) });
      const result = await response.json();
      setMessage(result.ok ? "Test gateway capture accepted. Refresh to check ERP processing." : result.error.message);
      await refreshOrder();
    } finally { setBusy(false); }
  }
  const inputClass = "w-full rounded border border-line bg-surface p-3 text-ink";
  return <main className="mx-auto max-w-3xl space-y-8 px-6 py-12">
    <h1 className="font-serif text-3xl">Your dropshipping cart</h1>
    <p className="rounded border border-line p-4 text-sm">TEST MODE · No real money is collected. Affiliate purchases take place on the merchant’s website.</p>
    <p role="status">{message}</p>
    {cart && <section className="space-y-4">{cart.lines.map((line) => <div key={line.product_slug} className="flex justify-between border-b border-line py-3"><span>{line.title} × {line.quantity}</span><span>{formatMoney(line.line_total)}</span></div>)}
      <p className="text-xl font-semibold">Total: {formatMoney(cart.total)}</p>
      <button onClick={() => { localStorage.removeItem("acom-cart"); setCart(undefined); }} className="underline">Clear cart</button>
    </section>}
    {!order && cart && <>
      <form onSubmit={signIn} className="space-y-3"><h2 className="text-xl">Sign in to your customer account</h2>
        <input name="email" type="email" aria-label="Sign-in email" placeholder="Email" required autoComplete="username" className={inputClass} />
        <input name="password" type="password" aria-label="Password" placeholder="Password" required autoComplete="current-password" className={inputClass} />
        <button disabled={busy} className="rounded border border-line px-5 py-2">Sign in</button>
      </form>
      <form onSubmit={checkout} className="space-y-3"><h2 className="text-xl">Delivery details</h2>
        {[ ["name", "Full name"], ["email", "Contact email"], ["phone", "Phone"], ["line1", "Address"], ["city", "City"], ["state", "State"], ["pincode", "PIN code"] ].map(([name, label]) => <label key={name} className="block">{label}<input name={name} required maxLength={140} type={name === "email" ? "email" : "text"} className={inputClass} /></label>)}
        <button disabled={busy} className="rounded bg-accent px-6 py-3 text-white">Create test checkout</button>
      </form>
    </>}
    {order && <section className="space-y-3 rounded border border-line p-6"><h2 className="text-xl">Order {order.checkout_id}</h2><p>Status: {order.status}</p>
      {order.status === "PendingPayment" && <button disabled={busy} onClick={simulatePayment} className="block rounded bg-accent px-5 py-3 text-white">Simulate test-gateway payment</button>}
      <button className="underline" onClick={refreshOrder}>Refresh payment and fulfillment status</button></section>}
  </main>;
}
