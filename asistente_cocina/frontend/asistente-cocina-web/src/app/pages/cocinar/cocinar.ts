// pages/cocinar/cocinar.ts

import { CommonModule } from '@angular/common';
import { Component, EventEmitter, Input, OnInit, Output } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { AsistenteCocinaService } from '../../services/asistente-cocina';

@Component({
  selector: 'app-cocinar',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './cocinar.html',
  styleUrl: './cocinar.scss'
})
export class Cocinar implements OnInit {
  @Input({ required: true }) receta: any;

  @Output() volver = new EventEmitter<void>();

  ingredientes: any[] = [];
  pasos: any[] = [];

  numeroRaciones: number | null = null;
  pesosCalculados: any[] = [];

  cocinando = false;
  pasoActualIndice = -1;

  modalCocinandoAbierto = false;

  ingredientesPreparados: Record<string, boolean> = {};

  cronometroActivo = false;
  segundosRestantes = 0;
  intervaloCronometro: any = null;

  error = '';

  constructor(private asistenteCocinaService: AsistenteCocinaService) {}

  ngOnInit(): void {
    this.cargarIngredientes();
    this.cargarPasos();
  }

  volverAtras(): void {
    this.volver.emit();
  }

  get pesoTotalIngredientes(): number {
    return this.pesosCalculados.reduce(
      (total, ingrediente) => total + ingrediente.peso,
      0
    );
  }

  get racionesCalculadas(): number {
    const pesoRacion = Number(this.receta?.pesoRacion || 0);

    if (pesoRacion <= 0) {
      return 0;
    }

    return this.pesoTotalIngredientes / pesoRacion;
  }


  cargarIngredientes(): void {
    this.asistenteCocinaService.obtenerIngredientesReceta(this.receta.id).subscribe({
      next: respuesta => {

        this.ingredientes = respuesta.content.sort(
          (a: any, b: any) => b.cantidad - a.cantidad
        );

        this.pesosCalculados = this.ingredientes.map(ingrediente => ({
          nombre: ingrediente.nombre,
          peso: Number(ingrediente.cantidad || 0),
          unidad: ingrediente.unidad || 'g'
        }));

        this.numeroRaciones = this.racionesCalculadas;

      },
      error: () => {
        this.error = 'No se pudieron cargar los ingredientes';
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


calcularPesosIngredientes(): void {
  const numeroRaciones = this.numeroRaciones ?? 0;

  if (numeroRaciones <= 0) {
    alert('Indica número de raciones');
    return;
  }

  if (!this.receta?.pesoRacion || this.receta.pesoRacion <= 0) {
    alert('La receta no tiene peso de ración configurado');
    return;
  }

  if (!this.ingredientes || this.ingredientes.length === 0) {
    alert('La receta no tiene ingredientes');
    return;
  }

  const pesoTotal = this.receta.pesoRacion * numeroRaciones;

  const ingredientesValidos = this.ingredientes.filter(
      ingrediente => Number(ingrediente.cantidad || 0) > 0
    );

    const ingredientesPeso = ingredientesValidos.filter(
      ingrediente => ingrediente.unidad === 'g'
    );

    const ingredientesUnidad = ingredientesValidos.filter(
      ingrediente => ingrediente.unidad !== 'g'
    );

    const totalBase = ingredientesPeso.reduce(
      (total, ingrediente) => total + Number(ingrediente.cantidad || 0),
      0
    );

    if (totalBase <= 0) {
      alert('La suma de ingredientes en gramos debe ser mayor que cero');
      return;
    }

    const factor = pesoTotal / totalBase;

    const pesosRecalculados = ingredientesPeso.map(ingrediente => ({
      nombre: ingrediente.nombre,
      peso: Math.round(Number(ingrediente.cantidad || 0) * factor),
      unidad: 'g'
    }));

    const unidadesSinRecalcular = ingredientesUnidad.map(ingrediente => ({
      nombre: ingrediente.nombre,
      peso: Number(ingrediente.cantidad || 0),
      unidad: ingrediente.unidad || 'unidad'
    }));

    this.pesosCalculados = [
      ...pesosRecalculados,
      ...unidadesSinRecalcular
    ];
  }

  iniciarCocinado(): void {
    if (this.pesosCalculados.length === 0) {
      alert('Primero calcula ingredientes');
      return;
    }

    this.ingredientesPreparados = {};

    this.pesosCalculados.forEach(ingrediente => {
      this.ingredientesPreparados[ingrediente.nombre] = false;
    });

    this.cocinando = true;
    this.modalCocinandoAbierto = true;
    this.pasoActualIndice = -1;
  }

  siguientePaso(): void {
    if (this.pasoActualIndice < this.pasos.length - 1) {
      this.pasoActualIndice++;
    } else {
      this.pasoActualIndice++;
    }
  }

  get mostrandoIngredientes(): boolean {
    return this.cocinando && this.pasoActualIndice === -1;
  }

  get pasoActual(): any | null {
    if (this.pasoActualIndice < 0) {
      return null;
    }

    return this.pasos[this.pasoActualIndice] ?? null;
  }

  get recetaTerminada(): boolean {
    return this.cocinando && this.pasoActualIndice >= this.pasos.length;
  }


  cerrarCocinado(): void {
  const confirmar = confirm('¿Cancelar la receta en curso?');

  if (!confirmar) {
    return;
  }

  this.cocinando = false;
  this.modalCocinandoAbierto = false;
  this.pasoActualIndice = -1;
  this.detenerCronometro();
  }

  pasoAnterior(): void {
    if (this.pasoActualIndice > -1) {
      this.pasoActualIndice--;
    }
  }

  get todosIngredientesPreparados(): boolean {
    return this.pesosCalculados.every(
      ingrediente => this.ingredientesPreparados[ingrediente.nombre]
    );
  }

  get numeroPasoVisible(): number {
    return this.pasoActualIndice + 2;
  }

  get nombrePasoVisible(): string {
    if (this.mostrandoIngredientes) {
      return 'Preparar ingredientes';
    }

    return this.pasoActual?.nombre ?? 'Receta terminada';
  }

  get hayCronometro(): boolean {
    return !!this.pasoActual?.duracion && this.pasoActual.duracion > 0;
  }

  iniciarCronometro(): void {
    if (!this.pasoActual?.duracion || this.pasoActual.duracion <= 0) {
      return;
    }

    this.segundosRestantes = this.pasoActual.duracion * 60;
    this.cronometroActivo = true;

    this.intervaloCronometro = setInterval(() => {
      this.segundosRestantes--;

      if (this.segundosRestantes <= 0) {
        this.detenerCronometro();
        alert('Cronómetro terminado');
      }
    }, 1000);
  }

  detenerCronometro(): void {
    if (this.intervaloCronometro) {
      clearInterval(this.intervaloCronometro);
      this.intervaloCronometro = null;
    }

    this.cronometroActivo = false;
  }

  get tiempoCronometro(): string {
    const minutos = Math.floor(this.segundosRestantes / 60);
    const segundos = this.segundosRestantes % 60;

    return `${minutos}:${segundos.toString().padStart(2, '0')}`;
  }
}