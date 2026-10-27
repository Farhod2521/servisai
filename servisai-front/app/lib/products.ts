"use client";

import { useEffect, useState } from "react";
import { api, type Product } from "./api";

// Bir sahifada bir nechta komponent so‘rasa ham backendga bitta so‘rov ketadi
let cache: Promise<Product[]> | null = null;

function load() {
  cache ??= api<Product[]>("/products").catch((e) => {
    cache = null; // keyingi urinishda qayta so‘raladi
    throw e;
  });
  return cache;
}

/** Admin mahsulotni o‘zgartirgandan keyin katalog yangi ma’lumotni olishi uchun */
export function invalidateProducts() {
  cache = null;
}

export function useProducts() {
  const [products, setProducts] = useState<Product[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    load()
      .then((list) => alive && setProducts(list))
      .catch((e: Error) => alive && setError(e.message));
    return () => {
      alive = false;
    };
  }, []);

  return { products, error, loading: products === null && error === null };
}
