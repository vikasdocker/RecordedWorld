#include "RWPlayerController.h"
#include "EnhancedInputComponent.h"
#include "EnhancedInputSubsystems.h"
#include "InputActionValue.h"
#include "Engine/LocalPlayer.h"

ARWPlayerController::ARWPlayerController()
{
	PrimaryActorTick.bCanEverTick = true;
}

void ARWPlayerController::BeginPlay()
{
	Super::BeginPlay();

	if (ULocalPlayer* LocalPlayer = GetLocalPlayer())
	{
		if (UEnhancedInputLocalPlayerSubsystem* InputSystem = LocalPlayer->GetSubsystem<UEnhancedInputLocalPlayerSubsystem>())
		{
			if (DefaultMappingContext)
			{
				InputSystem->AddMappingContext(DefaultMappingContext, 0);
			}
		}
	}

	UE_LOG(LogTemp, Log, TEXT("Player controller ready for user: %s"), *Username);
}

void ARWPlayerController::SetupInputComponent()
{
	Super::SetupInputComponent();

	if (UEnhancedInputComponent* EnhancedInput = Cast<UEnhancedInputComponent>(InputComponent))
	{
		if (MoveForwardAction)
		{
			EnhancedInput->BindAction(MoveForwardAction, ETriggerEvent::Triggered, this, &ARWPlayerController::MoveForward);
		}
		if (MoveRightAction)
		{
			EnhancedInput->BindAction(MoveRightAction, ETriggerEvent::Triggered, this, &ARWPlayerController::MoveRight);
		}
		if (LookUpAction)
		{
			EnhancedInput->BindAction(LookUpAction, ETriggerEvent::Triggered, this, &ARWPlayerController::LookUp);
		}
		if (TurnRightAction)
		{
			EnhancedInput->BindAction(TurnRightAction, ETriggerEvent::Triggered, this, &ARWPlayerController::TurnRight);
		}
	}
}

void ARWPlayerController::Tick(float DeltaTime)
{
	Super::Tick(DeltaTime);

	if (APawn* ControlledPawn = GetPawn())
	{
		FVector Velocity = ControlledPawn->GetVelocity();
		bIsMoving = Velocity.SizeSquared() > 1.0f;
	}
}

void ARWPlayerController::SetUsername(const FString& NewUsername)
{
	Username = NewUsername;
	UE_LOG(LogTemp, Log, TEXT("Username set to: %s"), *Username);
}

void ARWPlayerController::MoveForward(const FInputActionValue& Value)
{
	if (APawn* ControlledPawn = GetPawn())
	{
		const float Magnitude = Value.Get<float>();
		const FRotator Rotation = GetControlRotation();
		const FRotator YawRotation(0, Rotation.Yaw, 0);
		const FVector ForwardDirection = FRotationMatrix(YawRotation).GetUnitAxis(EAxis::X);
		ControlledPawn->AddMovementInput(ForwardDirection, Magnitude);
	}
}

void ARWPlayerController::MoveRight(const FInputActionValue& Value)
{
	if (APawn* ControlledPawn = GetPawn())
	{
		const float Magnitude = Value.Get<float>();
		const FRotator Rotation = GetControlRotation();
		const FRotator YawRotation(0, Rotation.Yaw, 0);
		const FVector RightDirection = FRotationMatrix(YawRotation).GetUnitAxis(EAxis::Y);
		ControlledPawn->AddMovementInput(RightDirection, Magnitude);
	}
}

void ARWPlayerController::LookUp(const FInputActionValue& Value)
{
	AddPitchInput(Value.Get<float>());
}

void ARWPlayerController::TurnRight(const FInputActionValue& Value)
{
	AddYawInput(Value.Get<float>());
}
