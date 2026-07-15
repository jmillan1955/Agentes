import { ComponentFixture, TestBed } from '@angular/core/testing';

import { Cocinar } from './cocinar';

describe('Cocinar', () => {
  let component: Cocinar;
  let fixture: ComponentFixture<Cocinar>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [Cocinar]
    })
    .compileComponents();

    fixture = TestBed.createComponent(Cocinar);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
