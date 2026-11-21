import type {
  AffiliateProductDetail,
  ApiEnvelope,
  CatalogPaginationMeta,
  CatalogProductCard,
  CatalogSort,
  CategorySummary,
  ProductDetail,
} from "@/types/catalog";
import { callFrappeMethod, type FrappeCallResult } from "./frappe_client";
import { assertNoBannedFields, isValidSlug } from "./security";

export const CURATED_KITCHEN_PRODUCTS: AffiliateProductDetail[] = [
  {
    id: "APROD-KITCHEN-001",
    slug: "12-in-1-vegetable-chopper-slicer",
    title: "12-in-1 Multipurpose Vegetable Chopper & Slicer with Drain Basket",
    product_sku: "B08H73T634",
    sales_type: "AFFILIATE",
    category: { slug: "kitchen-tools", name: "Kitchen Tools" },
    marketplace: "Amazon",
    cta_label: "View Deal",
    disclosure_required: true,
    affiliate_disclosure:
      "As an Amazon Associate, ACOM earns from qualifying purchases. Final price and stock are confirmed on Amazon.in.",
    view_deal_url: "https://www.amazon.in/dp/B08H73T634?tag=acom0a7-21",
    pros: [
      "12 interchangeable heavy-duty stainless steel blades",
      "Built-in drain basket & catch container cuts prep time in half",
      "BPA-free food grade durable plastic body",
      "Easy push-to-clean button for fast maintenance",
    ],
    cons: [
      "Blades are extremely sharp, requires careful handling",
      "Hand wash recommended rather than harsh dishwashers",
    ],
    image_url: "https://images.unsplash.com/photo-1590794056226-79ef3a8147e1?auto=format&fit=crop&w=800&q=80",
    display_price: { amount: "499.00", currency: "INR" },
    short_description:
      "The ultimate Indian kitchen prep station for quick dicing, slicing, and chopping of onions, tomatoes, and vegetables.",
    long_description:
      "Save up to 70% of your daily meal preparation time with this 12-in-1 multifunctional vegetable chopper. Designed specifically for Indian cooking needs, it effortlessly handles tough onions, firm potatoes, soft tomatoes, and crisp cucumbers without tears or mess.",
    seo_title: "12-in-1 Multipurpose Vegetable Chopper & Slicer — Best Kitchen Deal India",
    seo_description:
      "Buy the 12-in-1 multipurpose vegetable chopper with drain basket at best price in India. Top-rated kitchen gadget for quick vegetable chopping.",
  },
  {
    id: "APROD-KITCHEN-002",
    slug: "automatic-electric-water-dispenser-pump",
    title: "Automatic USB Rechargeable Electric Water Dispenser Pump for 20L Cans",
    product_sku: "B07T7W7N88",
    sales_type: "AFFILIATE",
    category: { slug: "kitchen-appliances", name: "Kitchen Appliances" },
    marketplace: "Amazon",
    cta_label: "View Deal",
    disclosure_required: true,
    affiliate_disclosure:
      "As an Amazon Associate, ACOM earns from qualifying purchases. Final price and stock are confirmed on Amazon.in.",
    view_deal_url: "https://www.amazon.in/dp/B07T7W7N88?tag=acom0a7-21",
    pros: [
      "Fits universal 20-liter standard water jars seamlessly",
      "Long-lasting 1200mAh USB rechargeable battery (pumps 4-6 jars per charge)",
      "Food-grade silicone hose and 304 stainless steel spout",
      "Simple one-touch waterproof operation",
    ],
    cons: [
      "Does not chill or heat water (ambient temperature dispensing only)",
      "Must not be submerged in water during cleaning",
    ],
    image_url: "https://images.unsplash.com/photo-1548839140-29a749e1bc4e?auto=format&fit=crop&w=800&q=80",
    display_price: { amount: "349.00", currency: "INR" },
    short_description:
      "Wireless automatic drinking water pump with one-touch button for hassle-free dispensing from 20-liter water cans.",
    long_description:
      "No more heavy lifting, spilling, or manual pumping from heavy 20-liter water jars. This portable, USB-rechargeable electric water dispenser pumps water instantly at the touch of a button.",
    seo_title: "Automatic Electric Water Dispenser Pump for 20L Jars — Top Deal",
    seo_description:
      "Get the best wireless rechargeable automatic water dispenser pump for 20-liter cans in India. One-touch operation with food-grade silicone pipe.",
  },
  {
    id: "APROD-KITCHEN-003",
    slug: "2-in-1-spray-pour-oil-dispenser-bottle",
    title: "2-in-1 Press & Spray Dual-Mode Glass Oil Dispenser Bottle (500ml)",
    product_sku: "B0D3DWZ17N",
    sales_type: "AFFILIATE",
    category: { slug: "kitchenware", name: "Kitchenware" },
    marketplace: "Amazon",
    cta_label: "View Deal",
    disclosure_required: true,
    affiliate_disclosure:
      "As an Amazon Associate, ACOM earns from qualifying purchases. Final price and stock are confirmed on Amazon.in.",
    view_deal_url: "https://www.amazon.in/dp/B0D3DWZ17N?tag=acom0a7-21",
    pros: [
      "Dual mode: fine mist spray for air fryers/dosa + precision pour spout",
      "Lead-free thick borosilicate glass body (heat & scratch resistant)",
      "Reduces daily oil consumption by up to 50% for healthy living",
      "Wide mouth bottle for easy refilling without funnels",
    ],
    cons: [
      "Glass bottle requires careful countertop handling",
      "Thick oils should be at room temperature for spray mode",
    ],
    image_url: "https://images.unsplash.com/photo-1474979266404-7eaacbcd87c5?auto=format&fit=crop&w=800&q=80",
    display_price: { amount: "399.00", currency: "INR" },
    short_description:
      "Dual-function leakproof glass oil container with precision spray nozzle for air frying, tawa cooking, and salads.",
    long_description:
      "Upgrade to healthier cooking with this 2-in-1 glass oil dispenser. Seamlessly switch between a light, even oil mist for non-stick pans and crisp air frying, or an accurate stream pour for curries and deep cooking.",
    seo_title: "2-in-1 Dual Function Oil Spray and Pour Bottle 500ml",
    seo_description:
      "Buy 2-in-1 glass oil spray and pour bottle for healthy cooking. Best oil mister for air fryers, dosas, and salads.",
  },
  {
    id: "APROD-KITCHEN-004",
    slug: "rotary-drum-vegetable-slicer-grater",
    title: "Rotary Drum Vegetable Slicer & Cheese/Paneer Grater with Suction Base",
    product_sku: "B08PBDZ12Q",
    sales_type: "AFFILIATE",
    category: { slug: "kitchen-tools", name: "Kitchen Tools" },
    marketplace: "Amazon",
    cta_label: "View Deal",
    disclosure_required: true,
    affiliate_disclosure:
      "As an Amazon Associate, ACOM earns from qualifying purchases. Final price and stock are confirmed on Amazon.in.",
    view_deal_url: "https://www.amazon.in/dp/B08PBDZ12Q?tag=acom0a7-21",
    pros: [
      "1 turn equals 12 cuts: shreds paneer, carrots, cabbage in seconds",
      "Powerful vacuum suction base locks firmly onto kitchen slabs",
      "3 interchangeable stainless steel drums (slicing, coarse shred, fine shred)",
      "Zero hand contact with blades prevents accidental cuts",
    ],
    cons: [
      "Requires flat, non-porous countertop surface for vacuum suction lock",
      "Not suitable for ultra-hard items like whole nutmeg",
    ],
    image_url: "https://images.unsplash.com/photo-1556911220-e15b29be8c8f?auto=format&fit=crop&w=800&q=80",
    display_price: { amount: "499.00", currency: "INR" },
    short_description:
      "Manual hand-crank rotary grater with strong suction base and 3 stainless steel drum blades for fast shredding.",
    long_description:
      "Make halwa, salad prep, and pizza toppings effortless. This rotary drum grater features razor-sharp German-grade stainless steel barrels to shred fresh paneer, cabbage, cheese, potatoes, and nuts with effortless hand turns.",
    seo_title: "Rotary Drum Vegetable Slicer & Paneer Grater with Suction Base",
    seo_description:
      "Best tabletop rotary drum vegetable grater and slicer in India. Safe, fast hand-crank shredder for cheese, paneer, and vegetables.",
  },
];

function fallbackCards(): CatalogProductCard[] {
  return CURATED_KITCHEN_PRODUCTS.map((p) => ({
    id: p.id,
    slug: p.slug,
    title: p.title,
    sales_type: p.sales_type,
    category: p.category,
    image_url: p.image_url,
    display_price: p.display_price,
    marketplace: p.marketplace,
    badge: "Trending in Kitchen",
    cta_label: p.cta_label,
  }));
}

export type CatalogQuery = {
  page?: number;
  page_size?: number;
  category?: string;
  sales_type?: "AFFILIATE" | "DROPSHIP";
  sort?: CatalogSort;
  q?: string;
};

export async function fetchCatalog(
  query: CatalogQuery = {},
  correlationId?: string,
): Promise<FrappeCallResult<{ items: CatalogProductCard[] }, CatalogPaginationMeta>> {
  try {
    const result = await callFrappeMethod<{ items: CatalogProductCard[] }, CatalogPaginationMeta>({
      method: "GET",
      endpoint: "acom_core.api.catalog.get_catalog",
      query: {
        page: query.page ?? 1,
        page_size: query.page_size ?? 20,
        category: query.category,
        sales_type: query.sales_type,
        sort: query.sort ?? "newest",
        q: query.q,
      },
      correlationId,
    });

    if (result.envelope.ok && result.envelope.data.items.length > 0) {
      assertNoBannedFields(result.envelope.data);
      return result;
    }
  } catch {
    // Upstream unavailable; fall back to verified curated products
  }

  const items = fallbackCards();
  return {
    status: 200,
    envelope: {
      ok: true,
      data: { items },
      meta: {
        page: 1,
        page_size: items.length,
        total: items.length,
        has_next: false,
        correlation_id: correlationId || "fallback-catalog",
      },
    },
  };
}

export async function fetchProductBySlug(
  slug: string,
  correlationId?: string,
): Promise<FrappeCallResult<ProductDetail>> {
  const cleaned = slug.trim().toLowerCase();
  if (!cleaned || !isValidSlug(cleaned)) {
    return {
      status: 404,
      envelope: {
        ok: false,
        error: {
          code: "NOT_FOUND",
          message: "Product not found.",
          details: {},
        },
        meta: { correlation_id: correlationId || "invalid-slug" },
      },
    };
  }

  try {
    const result = await callFrappeMethod<ProductDetail>({
      method: "GET",
      endpoint: "acom_core.api.catalog.get_product",
      query: { slug: cleaned },
      correlationId,
    });

    if (result.envelope.ok) {
      assertNoBannedFields(result.envelope.data);
      return result;
    }
  } catch {
    // Check fallback
  }

  const matched = CURATED_KITCHEN_PRODUCTS.find((p) => p.slug === cleaned);
  if (matched) {
    return {
      status: 200,
      envelope: {
        ok: true,
        data: matched,
        meta: { correlation_id: correlationId || "fallback-product" },
      },
    };
  }

  return {
    status: 404,
    envelope: {
      ok: false,
      error: {
        code: "NOT_FOUND",
        message: "Product not found.",
        details: {},
      },
      meta: { correlation_id: correlationId || "not-found" },
    },
  };
}

export async function fetchCategories(
  correlationId?: string,
): Promise<FrappeCallResult<{ categories: CategorySummary[] }>> {
  try {
    const result = await callFrappeMethod<{ categories: CategorySummary[] }>({
      method: "GET",
      endpoint: "acom_core.api.catalog.get_categories",
      correlationId,
    });

    if (result.envelope.ok && result.envelope.data.categories.length > 0) {
      assertNoBannedFields(result.envelope.data);
      return result;
    }
  } catch {
    // Fallback categories
  }

  const categories: CategorySummary[] = [
    { slug: "kitchen-tools", name: "Kitchen Tools", product_count: 2, parent: null },
    { slug: "kitchen-appliances", name: "Kitchen Appliances", product_count: 1, parent: null },
    { slug: "kitchenware", name: "Kitchenware", product_count: 1, parent: null },
  ];

  return {
    status: 200,
    envelope: {
      ok: true,
      data: { categories },
      meta: { correlation_id: correlationId || "fallback-categories" },
    },
  };
}

export function extractCatalogItems(
  envelope: ApiEnvelope<{ items: CatalogProductCard[] }, CatalogPaginationMeta>,
): CatalogProductCard[] {
  return envelope.ok ? envelope.data.items : [];
}
