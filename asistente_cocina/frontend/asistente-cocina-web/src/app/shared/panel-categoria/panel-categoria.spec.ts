import { ComponentFixture, TestBed } from '@angular/core/testing';

import { PanelCategoria } from './panel-categoria';

describe('PanelCategoria', () => {
  let component: PanelCategoria;
  let fixture: ComponentFixture<PanelCategoria>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [PanelCategoria]
    })
    .compileComponents();

    fixture = TestBed.createComponent(PanelCategoria);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
