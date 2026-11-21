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
    slug: "automatic-electric-water-dispenser-pump",
    title: "Automatic Wireless Water Dispenser Pump for 20 Litre Bottle (USB Rechargeable)",
    product_sku: "B0HL4P1CW1",
    sales_type: "AFFILIATE",
    category: { slug: "kitchen-appliances", name: "Kitchen Appliances" },
    marketplace: "Amazon",
    cta_label: "View Deal",
    disclosure_required: true,
    affiliate_disclosure:
      "As an Amazon Associate, ACOM earns from qualifying purchases. Final price and stock are confirmed on Amazon.in.",
    view_deal_url: "https://www.amazon.in/dp/B0HL4P1CW1?tag=acom0a7-21",
    pros: [
      "Fits universal standard 20-litre & 19-litre water cans effortlessly",
      "Long-lasting 1200mAh USB rechargeable battery (pumps 4-6 water jars per charge)",
      "Food-grade silicone hose and 304 stainless steel spout pipe",
      "One-touch waterproof switch for instant hands-free dispensing",
    ],
    cons: [
      "Dispenses ambient temperature water (does not heat or chill)",
      "Do not submerge the pump unit in water while cleaning",
    ],
    image_url: "https://m.media-amazon.com/images/I/61mi83F8-LL.jpg",
    images: [
      "https://m.media-amazon.com/images/I/61mi83F8-LL.jpg",
      "https://m.media-amazon.com/images/I/717bFmRoqLL.jpg",
      "https://m.media-amazon.com/images/I/711K0hREfaL.jpg",
      "https://m.media-amazon.com/images/I/81fZf5fFG2L.jpg",
      "https://m.media-amazon.com/images/I/71UP87xjfuL.jpg",
    ],
    display_price: { amount: "229.00", currency: "INR" },
    short_description:
      "Wireless automatic drinking water pump with one-touch button for hassle-free dispensing from 20-liter water cans.",
    long_description:
      "No more heavy lifting, spilling, or manual pumping from heavy 20-liter water jars. This portable, USB-rechargeable electric water dispenser pumps water instantly at the touch of a button. Features food-grade silicone tubing and durable battery life.",
    seo_title: "Automatic Wireless Water Dispenser Pump for 20L Cans — Top Deal",
    seo_description:
      "Buy wireless rechargeable automatic water dispenser pump for 20-liter bottles in India at ₹229. One-touch operation with food-grade silicone pipe.",
  },
  {
    id: "APROD-KITCHEN-002",
    slug: "12-in-1-vegetable-chopper-slicer",
    title: "Ganesh 14-in-1 Multipurpose Vegetable & Fruit Chopper with Stainless Steel Blades",
    product_sku: "B01BVDS1BE",
    sales_type: "AFFILIATE",
    category: { slug: "kitchen-tools", name: "Kitchen Tools" },
    marketplace: "Amazon",
    cta_label: "View Deal",
    disclosure_required: true,
    affiliate_disclosure:
      "As an Amazon Associate, ACOM earns from qualifying purchases. Final price and stock are confirmed on Amazon.in.",
    view_deal_url: "https://www.amazon.in/dp/B01BVDS1BE?tag=acom0a7-21",
    pros: [
      "14 interchangeable stainless steel cutting blades and graters",
      "Unbreakable food-grade body with built-in collection container",
      "Quick push-to-clean button for fast clearing of vegetable residue",
      "Cuts meal prep and vegetable dicing time by over 70%",
    ],
    cons: [
      "Blades are extremely sharp, always use hand safety guard",
      "Hand washing recommended for blade longevity",
    ],
    image_url: "https://m.media-amazon.com/images/I/41y4Ik5axHL.jpg",
    images: [
      "https://m.media-amazon.com/images/I/41y4Ik5axHL.jpg",
      "https://m.media-amazon.com/images/I/417hy14GFaL.jpg",
      "https://m.media-amazon.com/images/I/41e2S9+f8UL.jpg",
      "https://m.media-amazon.com/images/I/518paPwDcsL.jpg",
      "https://m.media-amazon.com/images/I/519mlJ4jNgL.jpg",
    ],
    display_price: { amount: "679.00", currency: "INR" },
    short_description:
      "The ultimate Indian kitchen prep station for quick dicing, slicing, and chopping of onions, tomatoes, and vegetables.",
    long_description:
      "Save up to 70% of your daily meal preparation time with this 14-in-1 multipurpose vegetable chopper. Designed specifically for Indian cooking needs, it effortlessly handles tough onions, firm potatoes, soft tomatoes, and crisp cucumbers without tears or mess.",
    seo_title: "14-in-1 Multipurpose Vegetable Chopper & Slicer — Best Kitchen Deal India",
    seo_description:
      "Buy the Ganesh multipurpose vegetable chopper at best price in India. Top-rated kitchen gadget for quick vegetable chopping.",
  },
  {
    id: "APROD-KITCHEN-003",
    slug: "2-in-1-spray-pour-oil-dispenser-bottle",
    title: "2-in-1 Dual-Mode Glass Oil Dispenser & Sprayer for Kitchen (500ml)",
    product_sku: "B0HKMZRTKG",
    sales_type: "AFFILIATE",
    category: { slug: "kitchenware", name: "Kitchenware" },
    marketplace: "Amazon",
    cta_label: "View Deal",
    disclosure_required: true,
    affiliate_disclosure:
      "As an Amazon Associate, ACOM earns from qualifying purchases. Final price and stock are confirmed on Amazon.in.",
    view_deal_url: "https://www.amazon.in/dp/B0HKMZRTKG?tag=acom0a7-21",
    pros: [
      "Dual mode: fine mist spray for air fryers/dosa + precision pour spout",
      "Lead-free thick borosilicate glass body (heat & scratch resistant)",
      "Reduces daily cooking oil consumption by up to 50% for healthy living",
      "Wide mouth bottle for easy refilling without funnels",
    ],
    cons: [
      "Glass bottle requires careful countertop handling",
      "Dense cooking oils should be kept at room temperature for optimal spray mist",
    ],
    image_url: "https://m.media-amazon.com/images/I/41GI9a+D3ZL.jpg",
    images: [
      "https://m.media-amazon.com/images/I/41GI9a+D3ZL.jpg",
      "https://m.media-amazon.com/images/I/41m6148pL0L.jpg",
      "https://m.media-amazon.com/images/I/51NLpcCAfnL.jpg",
      "https://m.media-amazon.com/images/I/41+LhV7RfIL.jpg",
      "https://m.media-amazon.com/images/I/51X4zyzvEUL.jpg",
    ],
    display_price: { amount: "189.00", currency: "INR" },
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
    slug: "pigeon-amaze-plus-electric-kettle-1-5l",
    title: "Pigeon by Stovekraft Amaze Plus 1.5L Stainless Steel Electric Kettle",
    product_sku: "B07WMS7TWB",
    sales_type: "AFFILIATE",
    category: { slug: "kitchen-appliances", name: "Kitchen Appliances" },
    marketplace: "Amazon",
    cta_label: "View Deal",
    disclosure_required: true,
    affiliate_disclosure:
      "As an Amazon Associate, ACOM earns from qualifying purchases. Final price and stock are confirmed on Amazon.in.",
    view_deal_url: "https://www.amazon.in/dp/B07WMS7TWB?tag=acom0a7-21",
    pros: [
      "1500W rapid boil boils 1.5 liters of water in under 5 minutes",
      "360-degree swivel base with cordless pouring convenience",
      "Automatic shut-off with dry boil protection for complete safety",
      "Premium mirror-finish food-grade stainless steel interior",
    ],
    cons: [
      "Body gets hot while boiling (use heat-resistant cool-touch handle)",
      "Cord length is optimized for countertop safety (~1 meter)",
    ],
    image_url: "https://m.media-amazon.com/images/I/61UhSgdSBDL.jpg",
    images: [
      "https://m.media-amazon.com/images/I/61UhSgdSBDL.jpg",
      "https://m.media-amazon.com/images/I/71OwY1Q2WPL.jpg",
      "https://m.media-amazon.com/images/I/71nY5irJjYL.jpg",
      "https://m.media-amazon.com/images/I/61ovEhLhpZL.jpg",
      "https://m.media-amazon.com/images/I/71NL+88ogCL.jpg",
    ],
    display_price: { amount: "489.00", currency: "INR" },
    short_description:
      "Classic stainless steel electric kettle with automatic shut-off and rapid 1500W boiling for tea, coffee, and noodles.",
    long_description:
      "India's best-selling electric kettle. The Pigeon Amaze Plus 1.5L kettle combines rapid heating with safety features including automatic cut-off and dry boil protection, ideal for quick morning tea, oatmeal, and boiled drinking water.",
    seo_title: "Pigeon Amaze Plus 1.5L Electric Kettle — Best Price India",
    seo_description:
      "Buy Pigeon Amaze Plus 1.5L stainless steel electric kettle with auto shut-off at best online price in India.",
  },
  {
    id: "APROD-KITCHEN-005",
    slug: "pigeon-handy-compact-vegetable-chopper",
    title: "Pigeon Handy and Compact 3-Blade Manual Vegetable Chopper (400ml)",
    product_sku: "B01LWYDEQ7",
    sales_type: "AFFILIATE",
    category: { slug: "kitchen-tools", name: "Kitchen Tools" },
    marketplace: "Amazon",
    cta_label: "View Deal",
    disclosure_required: true,
    affiliate_disclosure:
      "As an Amazon Associate, ACOM earns from qualifying purchases. Final price and stock are confirmed on Amazon.in.",
    view_deal_url: "https://www.amazon.in/dp/B01LWYDEQ7?tag=acom0a7-21",
    pros: [
      "Over 200,000+ 5-star ratings: India's #1 most popular kitchen gadget",
      "Requires zero electricity: smooth string pull mechanism",
      "3 high-precision stainless steel blades chop in under 10 pulls",
      "Compact, easy to wash, and travel-friendly",
    ],
    cons: [
      "400ml volume is ideal for 1-3 people (batch chopping needed for large parties)",
      "Avoid pulling cord to the extreme end to maintain spring tension",
    ],
    image_url: "https://m.media-amazon.com/images/I/41cVgYgAKpL.jpg",
    images: [
      "https://m.media-amazon.com/images/I/41cVgYgAKpL.jpg",
      "https://m.media-amazon.com/images/I/314y197f2rL.jpg",
      "https://m.media-amazon.com/images/I/41pZoaJINAL.jpg",
      "https://m.media-amazon.com/images/I/51PfXlJiYTL.jpg",
      "https://m.media-amazon.com/images/I/51S+DCyw3PL.jpg",
    ],
    display_price: { amount: "262.00", currency: "INR" },
    short_description:
      "India's best-selling pull-cord mini vegetable chopper for instantaneous dicing of onions, garlic, and chillies without tears.",
    long_description:
      "Effortlessly chop onions, garlic, ginger, and vegetables in seconds with the Pigeon Handy Chopper. Powered by a durable pull-cord mechanism and 3 sharp stainless steel blades, it requires no electricity and takes seconds to clean.",
    seo_title: "Pigeon Handy and Compact Chopper (400ml) — Best Deal India",
    seo_description:
      "Buy Pigeon Mini Handy Chopper 400ml with 3 blades at ₹262. India's top-rated kitchen chopper on Amazon.",
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
    images: p.images,
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

  let items = fallbackCards();
  if (query.category) {
    const catSlug = query.category.toLowerCase();
    items = items.filter((item) => item.category.slug === catSlug);
  }
  if (query.sales_type) {
    items = items.filter((item) => item.sales_type === query.sales_type);
  }

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
    { slug: "kitchen-appliances", name: "Kitchen Appliances", product_count: 2, parent: null },
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
