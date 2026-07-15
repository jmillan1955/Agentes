// models/receta.model.ts

export type NombreReceta = string;
export type Categoria = string;

export interface Receta {
  nombre: NombreReceta;
  categoria: Categoria;
}