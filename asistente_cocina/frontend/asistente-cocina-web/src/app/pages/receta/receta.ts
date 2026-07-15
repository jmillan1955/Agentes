// pages/receta/receta.ts

import { CommonModule } from '@angular/common';
import { Component, EventEmitter, Input, OnInit, Output } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { AsistenteCocinaService } from '../../services/asistente-cocina';

@Component({
  selector: 'app-receta',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './receta.html',
  styleUrl: './receta.scss',
})
export class Receta implements OnInit {
  @Input({ required: true }) receta: any;

  @Output() volver = new EventEmitter<void>();

  ingredientes: any[] = [];
  pasos: any[] = [];

  ingredienteEditando: any = null;
  nombreIngredienteOriginal = '';

  panelIngredientesAbierto = true;
  panelPasosAbierto = false;

  nuevoIngredienteCantidad: number | null = null;
  nuevoIngredienteUnidad = '%';
  nuevoIngredienteNombre = '';

  nuevoPasoNombre = '';
  nuevoPasoCronometro = false;
  nuevoPasoDuracion: number | null = null;

  pasoEditando: any = null;
  ordenPasoOriginal: number | null = null;

  error = '';

  constructor(private asistenteCocinaService: AsistenteCocinaService) {}

  ngOnInit(): void {
    this.cargarIngredientes();
    this.cargarPasos();
  }

  volverAtras(): void {
    this.volver.emit();
  }

  toggleIngredientes(): void {
    this.panelIngredientesAbierto = !this.panelIngredientesAbierto;
  }

  togglePasos(): void {
    this.panelPasosAbierto = !this.panelPasosAbierto;
  }

  cargarIngredientes(): void {
    this.asistenteCocinaService.obtenerIngredientesReceta(this.receta.id).subscribe({
      next: respuesta => {

        this.ingredientes = respuesta.content.sort(
    (a: any, b: any) => b.cantidad - a.cantidad
  );

      },
      error: () => {
        this.error = 'No se pudieron cargar los ingredientes';
      }
    });
  }

  agregarIngrediente(): void {
    const nombre = this.nuevoIngredienteNombre.trim();

    if (!nombre || !this.nuevoIngredienteCantidad || this.nuevoIngredienteCantidad <= 0) {
      alert('Debes indicar cantidad y nombre');
      return;
    }

    this.asistenteCocinaService.agregarIngredienteReceta(this.receta.id, {
      cantidad: this.nuevoIngredienteCantidad,
      unidad: this.nuevoIngredienteUnidad,
      nombreIngrediente: nombre
    }).subscribe({
      next: () => {
        this.nuevoIngredienteCantidad = null;
        this.nuevoIngredienteUnidad = '%';
        this.nuevoIngredienteNombre = '';
        this.cargarIngredientes();
      },
      error: () => {
        this.error = 'No se pudo añadir el ingrediente';
      }
    });
  }


  editarIngrediente(ingrediente: any): void {
    this.ingredienteEditando = ingrediente;
    this.nombreIngredienteOriginal = ingrediente.nombre;

    this.nuevoIngredienteCantidad = ingrediente.cantidad;
    this.nuevoIngredienteUnidad = ingrediente.unidad;
    this.nuevoIngredienteNombre = ingrediente.nombre;
  }

  cancelarEdicionIngrediente(): void {
    this.ingredienteEditando = null;
    this.nombreIngredienteOriginal = '';

    this.nuevoIngredienteCantidad = null;
    this.nuevoIngredienteUnidad = '%';
    this.nuevoIngredienteNombre = '';
  }

  guardarIngrediente(): void {
    const nombre = this.nuevoIngredienteNombre.trim();

    if (!nombre || !this.nuevoIngredienteCantidad || this.nuevoIngredienteCantidad <= 0) {
      alert('Debes indicar cantidad y nombre');
      return;
    }

    if (!this.ingredienteEditando) {
      this.agregarIngrediente();
      return;
    }

    this.asistenteCocinaService.actualizarIngredienteReceta(
      this.receta.id,
      this.nombreIngredienteOriginal,
      {
        cantidad: this.nuevoIngredienteCantidad,
        unidad: this.nuevoIngredienteUnidad,
        nombreIngrediente: nombre
      }
    ).subscribe({
      next: () => {
        this.cancelarEdicionIngrediente();
        this.cargarIngredientes();
      },
      error: () => {
        this.error = 'No se pudo actualizar el ingrediente';
      }
    });
  }

  eliminarIngrediente(ingrediente: any): void {
    const confirmar = confirm(`¿Eliminar ingrediente "${ingrediente.nombre}"?`);

    if (!confirmar) {
      return;
    }

    this.asistenteCocinaService.eliminarIngredienteReceta(
      this.receta.id,
      ingrediente.nombre
    ).subscribe({
      next: () => {
        this.cargarIngredientes();

        if (this.ingredienteEditando === ingrediente) {
          this.cancelarEdicionIngrediente();
        }
      },
      error: () => {
        this.error = 'No se pudo eliminar el ingrediente';
      }
    });
  }

  cargarPasos(): void {
    this.asistenteCocinaService.obtenerPasosReceta(this.receta.id).subscribe({
      next: respuesta => {
        this.pasos = respuesta.content;
      },
      error: () => {
        this.error = 'No se pudieron cargar los pasos';
      }
    });
  }

  agregarPaso(): void {
    const nombre = this.nuevoPasoNombre.trim();

    const duracion = this.nuevoPasoCronometro
      ? Number(this.nuevoPasoDuracion || 0)
      : 0;

    if (!nombre) {
      alert('Debes indicar la descripción del paso');
      return;
    }

    if (this.nuevoPasoCronometro && duracion <= 0) {
      alert('Si activas cronómetro debes indicar una duración mayor que cero');
      return;
    }

    this.asistenteCocinaService.agregarPasoReceta(this.receta.id, {
      nombre,
      duracion,
      sonido: '',
      operaciones: []
    }).subscribe({
      next: () => {
        this.nuevoPasoNombre = '';
        this.nuevoPasoCronometro = false;
        this.nuevoPasoDuracion = null;
        this.cargarPasos();
      },
      error: () => {
        this.error = 'No se pudo añadir el paso';
      }
    });
  }

  editarPaso(paso: any): void {
    this.pasoEditando = paso;
    this.ordenPasoOriginal = paso.orden;

    this.nuevoPasoNombre = paso.nombre;
    this.nuevoPasoDuracion = paso.duracion && paso.duracion > 0
      ? paso.duracion
      : null;

    this.nuevoPasoCronometro = !!paso.duracion && paso.duracion > 0;
  }

  cancelarEdicionPaso(): void {
    this.pasoEditando = null;
    this.ordenPasoOriginal = null;

    this.nuevoPasoNombre = '';
    this.nuevoPasoCronometro = false;
    this.nuevoPasoDuracion = null;
  }


  guardarPaso(): void {
    const nombre = this.nuevoPasoNombre.trim();

    const duracion = this.nuevoPasoCronometro
      ? Number(this.nuevoPasoDuracion || 0)
      : 0;

    if (!nombre) {
      alert('Debes indicar la descripción del paso');
      return;
    }

    if (this.nuevoPasoCronometro && duracion <= 0) {
      alert('Si activas cronómetro debes indicar una duración mayor que cero');
      return;
    }

    if (!this.pasoEditando || this.ordenPasoOriginal === null) {
      this.agregarPaso();
      return;
    }

    this.asistenteCocinaService.actualizarPasoReceta(
      this.receta.id,
      this.ordenPasoOriginal,
      {
        orden: this.ordenPasoOriginal,
        nombre,
        duracion,
        sonido: '',
        operaciones: this.pasoEditando.operaciones ?? []
      }
    ).subscribe({
      next: () => {
        this.cancelarEdicionPaso();
        this.cargarPasos();
      },
      error: () => {
        this.error = 'No se pudo actualizar el paso';
      }
    });
  }
  
  eliminarPaso(paso: any): void {
    const confirmar = confirm(`¿Eliminar paso "${paso.nombre}"?`);

    if (!confirmar) {
      return;
    }

    this.asistenteCocinaService.eliminarPasoReceta(
      this.receta.id,
      paso.orden
    ).subscribe({
      next: () => {
        if (this.pasoEditando === paso) {
          this.cancelarEdicionPaso();
        }

        this.cargarPasos();
      },
      error: () => {
        this.error = 'No se pudo eliminar el paso';
      }
    });
  }







}