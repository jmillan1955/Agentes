// services/asistente-cocina.ts

import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
interface ApiResponse<T> {
  content: T;
}


@Injectable({
  providedIn: 'root'
})
export class AsistenteCocinaService {

   //private apiUrl = 'http://localhost:5000/api';
   private apiUrl = '/api';
  //private apiUrl = 'http://192.168.1.131/api';
  private agenteCocinaUrl = '/agente-cocina';
  constructor(private http: HttpClient) {}

  // =========================
  // CATEGORÍAS
  // =========================

  obtenerCategorias(): Observable<string[]> {
    return this.http.get<string[]>(
      `${this.apiUrl}/categorias`
    );
  }

  // =========================
  // RECETAS
  // =========================

  obtenerRecetas(): Observable<ApiResponse<any[]>>  {
    return this.http.get<ApiResponse<any[]>>(
      `${this.apiUrl}/recetas`
    );
  }

  obtenerReceta(id: number): Observable<any> {
    return this.http.get<ApiResponse<any[]>>(
      `${this.apiUrl}/recetas/${id}`
    );
  }

  obtenerTodasRecetas(): Observable<any[]> {
    return this.http.get<any[]>(
      `${this.apiUrl}/recetas`
    );
  }


  obtenerRecetasPorCategoria(categoria: string): Observable<any[]> {
    return this.http.get<any[]>(
      `${this.apiUrl}/recetas/por-categoria?categoria=${encodeURIComponent(categoria)}`
    );
  }

  crearReceta(request: {
    nombre: string;
    categoria: string;
    pesoRacion: number;
  }): Observable<any> {
    return this.http.post(
      `${this.apiUrl}/recetas`,
      request
    );
  }

  actualizarReceta(
    id: number,
    receta: { nombre: string; pesoRacion: number }
  ) {
    return this.http.put(`${this.apiUrl}/recetas/${id}`, receta);
  }

  eliminarReceta(recetaId: number): Observable<void> {
    return this.http.delete<void>(
      `${this.apiUrl}/recetas/${recetaId}`
    );
  }

  // =========================
  // INGREDIENTES
  // =========================

  obtenerIngredientesReceta(recetaId: number): Observable<ApiResponse<any[]>> {
    return this.http.get<ApiResponse<any[]>>(
      `${this.apiUrl}/recetas/${recetaId}/ingredientes`
    );
  }

  agregarIngredienteReceta(
    recetaId: number,
    request: {
      cantidad: number;
      unidad: string;
      nombreIngrediente: string;
    }
  ): Observable<void> {
    return this.http.post<void>(
      `${this.apiUrl}/recetas/${recetaId}/ingredientes`,
      request
    );
  }

  // =========================
  // PASOS
  // =========================

  obtenerPasosReceta(recetaId: number): Observable<ApiResponse<any[]>> {
    return this.http.get<ApiResponse<any[]>>(
      `${this.apiUrl}/recetas/${recetaId}/pasos`
    );
  }

  agregarPasoReceta(
    recetaId: number,
    request: {
      nombre: string;
      duracion: number;
      sonido: string;
      operaciones: any[];
    }
  ): Observable<void> {
    return this.http.post<void>(
      `${this.apiUrl}/recetas/${recetaId}/pasos`,
      request
    );
  }

  // =========================
  // ELABORACIÓN
  // =========================

  obtenerElaboracion(recetaId: number): Observable<string> {
    return this.http.get(
      `${this.apiUrl}/recetas/${recetaId}/elaboracion`,
      {
        responseType: 'text'
      }
    );
  }

  actualizarIngredienteReceta(
    recetaId: number,
    nombreOriginal: string,
    request: {
      cantidad: number;
      unidad: string;
      nombreIngrediente: string;
    }
  ): Observable<void> {
    return this.http.put<void>(
      `${this.apiUrl}/recetas/${recetaId}/ingredientes?nombreOriginal=${encodeURIComponent(nombreOriginal)}`,
      request
    );
  }

  eliminarIngredienteReceta(
    recetaId: number,
    nombreIngrediente: string
  ): Observable<void> {
    return this.http.delete<void>(
      `${this.apiUrl}/recetas/${recetaId}/ingredientes?nombre=${encodeURIComponent(nombreIngrediente)}`
    );
  }

  eliminarPasoReceta(
    recetaId: number,
    orden: number
  ): Observable<void> {
    return this.http.delete<void>(
      `${this.apiUrl}/recetas/${recetaId}/pasos/${orden}`
    );
  }

  actualizarPasoReceta(
    recetaId: number,
    orden: number,
    request: {
      orden: number;
      nombre: string;
      duracion: number;
      sonido: string;
      operaciones: any[];
    }
  ): Observable<void> {
    return this.http.put<void>(
      `${this.apiUrl}/recetas/${recetaId}/pasos/${orden}`,
      request
    );
  }


// =========================
// AGENTE COCINA
// =========================

iniciarCocinadoAgente(
  recetaId: number,
  raciones: number
): Observable<any> {
  return this.http.post(
    `${this.agenteCocinaUrl}/cocina/iniciar`,
    {
      receta_id: recetaId,
      raciones
    }
  );
}

siguientePasoAgente(): Observable<any> {
  return this.http.post(
    `${this.agenteCocinaUrl}/cocina/siguiente`,
    {}
  );
}

repetirPasoAgente(): Observable<any> {
  return this.http.post(
    `${this.agenteCocinaUrl}/cocina/repetir`,
    {}
  );
}

finalizarCocinadoAgente(): Observable<any> {
  return this.http.post(
    `${this.agenteCocinaUrl}/cocina/finalizar`,
    {}
  );
}

obtenerEstadoAgente(): Observable<any> {
  return this.http.get(
    `${this.agenteCocinaUrl}/cocina/estado`
  );
}





}